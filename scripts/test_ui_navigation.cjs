const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const test = require("node:test");
const { navigateInterface } = require("./ui_navigation.cjs");

const origin = "https://interface.example";
const paths = ["auth/me", "models", "conversations", "knowledge/documents"];
const request = (path, method = "GET") => ({ method: () => method, url: origin + "/api/v1/" + path });
const response = (req, status = 200, failure = null) => ({
  request: () => req, url: () => req.url, status: () => status,
  finished: async () => failure,
});

class Page extends EventEmitter {
  constructor(visit) { super(); this.visit = visit; }
  waitForResponse(predicate, { timeout }) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.off("response", receive); reject(Error("Missing current response")); }, timeout);
      const receive = (value) => {
        if (!predicate(value)) return;
        clearTimeout(timer); this.off("response", receive); resolve(value);
      };
      this.on("response", receive);
    });
  }
  async goto() {
    await this.visit(this);
    return { status: () => 200, url: () => origin + "/" };
  }
  getByLabel() { return { waitFor: async () => {} }; }
  receive(req, status = 200, failure = null) {
    this.emit("request", req);
    this.emit("response", response(req, status, failure));
  }
}

test("a previous page's delayed 401 cannot reject the current successful visit", async () => {
  const old = request("auth/me");
  const page = new Page(async (page) => {
    page.emit("response", response(old, 401));
    for (const path of paths) page.receive(request(path));
  });
  assert.equal((await navigateInterface(page, origin)).status(), 200);
  assert.equal(page.listenerCount("request"), 0);
});

test("old successful responses cannot qualify a visit with no current data", async () => {
  const old = paths.map((path) => response(request(path)));
  const page = new Page(async (page) => { for (const value of old) page.emit("response", value); });
  await assert.rejects(navigateInterface(page, origin, "/", { timeout: 20 }), /Missing current response/);
  assert.equal(page.listenerCount("request"), 0);
});

for (const [status, failure] of [[401, null], [503, null], [200, Error("Body interrupted")]]) {
  test(`a current response still fails qualification: ${status}, interrupted=${Boolean(failure)}`, async () => {
    const page = new Page(async (page) => {
      for (const path of paths) page.receive(request(path), path === "auth/me" ? status : 200, path === "auth/me" ? failure : null);
    });
    await assert.rejects(navigateInterface(page, origin), /Required interface data response failed/);
    assert.equal(page.listenerCount("request"), 0);
  });
}

test("a POST response cannot substitute for required interface GET data", async () => {
  const page = new Page(async (page) => { for (const path of paths) page.receive(request(path, "POST")); });
  await assert.rejects(navigateInterface(page, origin, "/", { timeout: 20 }), /Missing current response/);
  assert.equal(page.listenerCount("request"), 0);
});

test("failed navigation removes request observation", async () => {
  const page = new Page(async () => { throw Error("Navigation unavailable"); });
  await assert.rejects(navigateInterface(page, origin, "/", { timeout: 20 }), /Navigation unavailable/);
  assert.equal(page.listenerCount("request"), 0);
});

test("shared sign-in observes the real account entry without requiring a native password field", async () => {
  const page = new Page(async () => {});
  page.getByLabel = () => assert.fail("Native credentials must not be required for shared entry");
  page.getByRole = (role, options) => {
    assert.equal(role, "button");
    assert.equal(options.name, "Continue with Onesa");
    return {waitFor: async () => {}};
  };
  assert.equal((await navigateInterface(page, origin, "/", {authentication: true, sharedIdentity: true})).status(), 200);
});

test("shared account settings retain both fresh authenticated data gates", async () => {
  for (const status of [200, 503]) {
    const page = new Page(async () => {});
    page.goto = async () => {
      page.receive(request("auth/me"));
      page.receive(request("auth/sessions"), status);
      return {status: () => 200, url: () => origin + "/settings"};
    };
    page.getByRole = (role, options) => {
      assert.equal(role, "heading");
      assert.equal(options.name, "Your Onesa account");
      assert.equal(options.level, 2);
      return {waitFor: async () => {}};
    };
    const observed = navigateInterface(page, origin, "/settings", {sharedIdentity: true, timeout: 20});
    if (status === 200) assert.equal((await observed).status(), 200);
    else await assert.rejects(observed, /Required interface data response failed/);
  }
});
