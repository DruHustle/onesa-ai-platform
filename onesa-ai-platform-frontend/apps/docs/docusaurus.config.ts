import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type {Options, ThemeConfig} from '@docusaurus/preset-classic';
const lightCodeColors:Record<string,string>={'#999988':'#586069','#e3116c':'#a31545','#36acaa':'#006a67','#00a4db':'#005f86','#d73a49':'#982f3b'};
const lightCodeTheme={...prismThemes.github,styles:prismThemes.github.styles.map(rule=>({...rule,style:{...rule.style,color:lightCodeColors[rule.style.color||'']||rule.style.color}}))};
const scope = process.env.ONESA_DOCS_SCOPE === 'internal' ? 'internal' : 'public';
const internal = scope === 'internal';
const staticHosting = process.env.ONESA_DOCS_STATIC_HOSTING === 'true';
const accessHosting = process.env.ONESA_DOCS_HOSTING === 'cloudflare-access';
if (accessHosting && !internal) throw new Error('Cloudflare Access hosting requires the internal documentation scope.');
if (staticHosting && internal) throw new Error('Internal documentation requires the authenticated gateway, not static hosting.');
const appUrl = process.env.ONESA_APPLICATION_URL || (staticHosting ? 'https://platform.onesa.eu' : 'http://localhost:3100');
const apiUrl = process.env.ONESA_DOCS_API_URL || '';
if (apiUrl && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(apiUrl)) {
  throw new Error('API execution is restricted to an explicitly configured loopback development origin.');
}
const config: Config = {
  title: 'Onesa', tagline: 'Engineering Intelligent Possibilities',
  url:process.env.ONESA_DOCS_URL || (staticHosting ? 'https://docs.onesa.eu' : `http://localhost:${internal ? 3201 : 3200}`), staticDirectories:['static', `.generated/${scope}/static`, `static-${scope}`], favicon:'favicon.ico', baseUrl:'/', organizationName:'Onesa AI', projectName:'onesa-ai-platform',
  scripts:[{src:'/automatic-day-night.js',async:false,defer:false}],
  onBrokenLinks:'throw', onBrokenAnchors:'throw', trailingSlash:false,
  markdown:{format:'md', mermaid:true}, themes:['@docusaurus/theme-mermaid'],
  customFields:{documentationVersion:'0.3.0', apiUrl, scope, appUrl, staticHosting:staticHosting || accessHosting},
  presets:[['classic', {docs:{numberPrefixParser:false,path:`.generated/${scope}/docs`, sidebarPath:'./sidebars.ts', showLastUpdateTime:false}, pages:{path:`.generated/${scope}/pages`}, blog:false, theme:{customCss:'./src/css/custom.css'}} satisfies Options]],
  themeConfig:{
    colorMode:{defaultMode:'light', respectPrefersColorScheme:false,disableSwitch:true},
    navbar:{title:'Onesa / Docs', items:[
      {to:'/architecture',label:'Architecture & Workflows',position:'left'},
      ...(internal ? [{to:'/onboarding',label:'Engineering Onboarding',position:'left' as const}] : []),
      {label:'Reference',position:'left',items:[{to:internal?'/docs':'/docs/public/introduction',label:'Documentation index'},{to:'/api-explorer',label:'API'},...(internal?[{to:'/database',label:'Database'}]:[]),{to:'/tutorials',label:'Guides'},{to:'/downloads',label:'Downloads'},{to:'/assistant',label:'Ask Onesa'}]},
      {type:'custom-automatic-day-night',position:'right'},
      {label:'Onesa applications',position:'right',items:[{href:'https://onesa.eu',label:'Onesa company'},{href:'https://portal.onesa.eu',label:'Company Portal'},{href:'https://robot.onesa.eu',label:'Robot interface'},{href:appUrl,label:'Onesa AI home'},{href:appUrl+'/knowledge',label:'Onesa Knowledge'},{href:appUrl+'/agents',label:'Onesa Agents'},{href:appUrl+'/travel',label:'Onesa Travel'}]},
      ...(internal?[{href:process.env.ONESA_PUBLIC_DOCUMENTATION_URL||'https://docs.onesa.eu',label:'Public docs ↗',position:'right' as const}]:[]),{type:'search',position:'right'}]},
    footer:{style:'dark', copyright:'Onesa UG · Engineering Intelligent Possibilities · Documentation v0.3.0'},
    prism:{theme:lightCodeTheme,additionalLanguages:['python','bash','json','sql','yaml','typescript']},
  } satisfies ThemeConfig,
};
export default config;
