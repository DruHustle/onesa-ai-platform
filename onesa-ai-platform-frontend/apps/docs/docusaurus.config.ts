import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type {Options, ThemeConfig} from '@docusaurus/preset-classic';
import {readdir, readFile, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import applications from '../../packages/onesa-design/onesa-applications.json';
import {resolveApplicationOrigin} from './src/lib/application-origin.mjs';
const lightCodeColors:Record<string,string>={'#999988':'#586069','#e3116c':'#a31545','#36acaa':'#006a67','#00a4db':'#005f86','#d73a49':'#982f3b'};
const lightCodeTheme={...prismThemes.github,styles:prismThemes.github.styles.map(rule=>({...rule,style:{...rule.style,color:lightCodeColors[rule.style.color||'']||rule.style.color}}))};
const scope = process.env.ONESA_DOCS_SCOPE === 'internal' ? 'internal' : 'public';
const internal = scope === 'internal';
const environment = process.env.ONESA_DOCS_ENVIRONMENT || (process.env.VERCEL_ENV === 'production' ? 'production' : process.env.VERCEL_ENV === 'preview' ? 'staging' : 'development');
if (!['development', 'staging', 'production'].includes(environment)) throw new Error('ONESA_DOCS_ENVIRONMENT must be development, staging or production.');
const staticHosting = process.env.ONESA_DOCS_STATIC_HOSTING === 'true';
const accessHosting = process.env.ONESA_DOCS_HOSTING === 'cloudflare-access';
if (accessHosting && !internal) throw new Error('Cloudflare Access hosting requires the internal documentation scope.');
if (staticHosting && internal) throw new Error('Internal documentation requires the authenticated gateway, not static hosting.');
const appUrl = resolveApplicationOrigin({configured:process.env.ONESA_APPLICATION_URL,
  docsUrl:process.env.ONESA_DOCS_URL,environment,staticHosting,accessHosting,
  publicOrigin:applications.applications.find(application=>application.id==='ai')!.href});
const publicDocsUrl = resolveApplicationOrigin({configured:process.env.ONESA_PUBLIC_DOCUMENTATION_URL || applications.applications.find(application=>application.id==='docs')!.href,
  docsUrl:process.env.ONESA_DOCS_URL,environment,staticHosting,accessHosting});
const apiUrl = process.env.ONESA_DOCS_API_URL || '';
if (apiUrl && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(apiUrl)) {
  throw new Error('API execution is restricted to an explicitly configured loopback development origin.');
}
const config: Config = {
  title: internal ? 'Onesa Engineering Docs' : 'Onesa Developer Docs', tagline: 'Engineering Intelligent Possibilities',
  url:process.env.ONESA_DOCS_URL || (staticHosting ? 'https://docs.onesa.eu' : `http://localhost:${internal ? 3201 : 3200}`), staticDirectories:['static', `.generated/${scope}/static`, `static-${scope}`], baseUrl:'/', organizationName:'Onesa AI', projectName:'onesa-ai-platform',
  headTags:[{tagName:'link',attributes:{rel:'icon',href:'/brand/icons/v1/onesa-docs.svg',type:'image/svg+xml',sizes:'any'}},{tagName:'link',attributes:{rel:'apple-touch-icon',href:'/brand/icons/v1/onesa-docs-180.png',type:'image/png',sizes:'180x180'}}],
  onBrokenLinks:'throw', onBrokenAnchors:'throw', trailingSlash:false,
  markdown:{format:'md', mermaid:true}, themes:['@docusaurus/theme-mermaid'],
  plugins:[function onesaProductContext(){return {name:'onesa-product-context',async postBuild({outDir}:{outDir:string}){const visit=async(directory:string):Promise<void>=>{for(const entry of await readdir(directory,{withFileTypes:true})){const file=join(directory,entry.name);if(entry.isDirectory())await visit(file);else if(entry.name.endsWith('.html')){const html=await readFile(file,'utf8');await writeFile(file,html.replace(/<html\b/,'<html data-onesa-product="docs"'));}}};await visit(outDir);}};}],
  customFields:{documentationVersion:'0.3.0', apiUrl, scope, appUrl, environment, staticHosting:staticHosting || accessHosting},
  presets:[['classic', {docs:{numberPrefixParser:false,path:`.generated/${scope}/docs`, sidebarPath:'./sidebars.ts', showLastUpdateTime:false}, pages:{path:`.generated/${scope}/pages`}, blog:false, theme:{customCss:'./src/css/custom.css'}} satisfies Options]],
  themeConfig:{
    colorMode:{defaultMode:'light', respectPrefersColorScheme:true,disableSwitch:true},
    navbar:{title:internal ? 'Onesa Engineering Docs' : 'Onesa Developer Docs', items:[
      {to:'/architecture',label:'Architecture & Workflows',position:'left'},
      ...(internal ? [{to:'/onboarding',label:'Engineering Onboarding',position:'left' as const},{to:'/docs/architecture/ONESA_DESIGN_SYSTEM',label:'Onesa Design System',position:'left' as const}] : []),
      {label:'Reference',position:'left',items:[{to:internal?'/docs':'/docs/public/introduction',label:'Documentation index'},{to:'/api-explorer',label:'API'},...(internal?[{to:'/database',label:'Database'}]:[]),{to:'/tutorials',label:'Guides'},{to:'/downloads',label:'Downloads'},{to:'/assistant',label:'Ask Onesa'}]},
      {label:'Onesa applications',position:'right',items:applications.applications.map(application=>({href:application.id==='ai'?appUrl:application.id==='docs'?publicDocsUrl:application.href,label:application.label}))},
      ...(internal?[{href:publicDocsUrl,label:'Public docs',position:'right' as const}]:[]),{type:'search',position:'right'}]},
    footer:{style:'dark', copyright:'Onesa UG · Engineering Intelligent Possibilities · Documentation v0.3.0'},
    prism:{theme:lightCodeTheme,additionalLanguages:['python','bash','json','sql','yaml','typescript']},
  } satisfies ThemeConfig,
};
export default config;
