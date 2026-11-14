/* A timing probe must not leave a synthetic edit behind and trigger discard UI. */
async function withTemporaryDraft(input, recordEditable) {
  const baseline = await input.inputValue();
  try {
    await input.fill("Unsent synthetic timing draft");
    await recordEditable();
  } finally {
    await input.fill(baseline);
  }
}
module.exports = { withTemporaryDraft };
