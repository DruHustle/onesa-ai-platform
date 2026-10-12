import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type {Options, ThemeConfig} from '@docusaurus/preset-classic';
const lightCodeColors:Record<string,string>={'#999988':'#586069','#e3116c':'#a31545','#36acaa':'#006a67','#00a4db':'#005f86','#d73a49':'#982f3b'};
const lightCodeTheme={...prismThemes.github,styles:prismThemes.github.styles.map(rule=>({...rule,style:{...rule.style,color:lightCodeColors[rule.style.color||'']||rule.style.color}}))};
const darkCodeTheme={...prismThemes.dracula,styles:prismThemes.dracula.styles.map(rule=>({...rule,style:{...rule.style,color:rule.style.color==='#6272a4'?'#aab3d0':rule.style.color}}))};
const scope = process.env.ONESA_DOCS_SCOPE === 'internal' ? 'internal' : 'public';
const internal = scope === 'internal';
const staticHosting = process.env.ONESA_DOCS_STATIC_HOSTING === 'true';
if (staticHosting && internal) throw new Error('Internal documentation requires the authenticated gateway, not static hosting.');
const appUrl = process.env.ONESA_APPLICATION_URL || (staticHosting ? 'https://platform.onesa.eu' : 'http://localhost:3100');
const apiUrl = process.env.ONESA_DOCS_API_URL || '';
if (apiUrl && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(apiUrl)) {
  throw new Error('API execution is restricted to an explicitly configured loopback development origin.');
}
const config: Config = {
  title: 'Onesa', tagline: 'Engineering Intelligent Possibilities',
  url:process.env.ONESA_DOCS_URL || (staticHosting ? 'https://docs.onesa.eu' : `http://localhost:${internal ? 3201 : 3200}`), staticDirectories:['static', `.generated/${scope}/static`, `static-${scope}`], favicon:'favicon.ico', baseUrl:'/', organizationName:'Onesa AI', projectName:'onesa-ai-platform',
  onBrokenLinks:'throw', trailingSlash:false,
  markdown:{format:'md', mermaid:true}, themes:['@docusaurus/theme-mermaid'],
  customFields:{documentationVersion:'0.3.0', apiUrl, scope, appUrl, staticHosting},
  presets:[['classic', {docs:{numberPrefixParser:false,path:`.generated/${scope}/docs`, sidebarPath:'./sidebars.ts', showLastUpdateTime:false}, pages:{path:`.generated/${scope}/pages`}, blog:false, theme:{customCss:'./src/css/custom.css'}} satisfies Options]],
  headTags:[{tagName:"script",attributes:{src:"/appearance.js"}}],
  themeConfig:{
    colorMode:{defaultMode:'light', respectPrefersColorScheme:false,disableSwitch:true},
    navbar:{title:'Onesa / Docs', items:[{to:internal?'/docs':'/docs/public/introduction',label:'Reference',position:'left'},{to:'/architecture',label:'Architecture',position:'left'},{to:'/api-explorer',label:'API',position:'left'},...(internal ? [{to:'/database',label:'Database',position:'left' as const}] : []),{to:'/tutorials',label:'Guides',position:'left'},{to:'/downloads',label:'Downloads',position:'left'},{to:'/assistant',label:'Ask Onesa',position:'left'},{label:'Onesa applications',position:'right',items:[{href:'https://onesa.eu',label:'Onesa company'},{href:'https://portal.onesa.eu',label:'Company Portal'},{href:'https://robot.onesa.eu',label:'Robot interface'},{href:appUrl,label:'Onesa AI home'},{href:appUrl,label:'Onesa Chat'},{href:appUrl+'/knowledge',label:'Onesa Knowledge'},{href:appUrl+'/agents',label:'Onesa Agents'},{href:appUrl+'/travel',label:'Onesa Travel'}]},...(internal?[{href:process.env.ONESA_PUBLIC_DOCUMENTATION_URL||'http://localhost:3200',label:'Developer docs ↗',position:'right' as const}]:[]),{type:'custom-appearance',position:'right'},{type:'search',position:'right'}]},
    footer:{style:'dark', copyright:'Onesa UG · Engineering Intelligent Possibilities · Documentation v0.3.0'},
    prism:{theme:lightCodeTheme,darkTheme:darkCodeTheme,additionalLanguages:['python','bash','json','sql','yaml','typescript']},
  } satisfies ThemeConfig,
};
export default config;
