import type {Config} from '@docusaurus/types';
import type {Options, ThemeConfig} from '@docusaurus/preset-classic';
const scope = process.env.ONESA_DOCS_SCOPE === 'internal' ? 'internal' : 'public';
const internal = scope === 'internal';
const appUrl = process.env.ONESA_APPLICATION_URL || 'http://localhost:3100';
const apiUrl = process.env.ONESA_DOCS_API_URL || '';
if (apiUrl && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(apiUrl)) {
  throw new Error('API execution is restricted to an explicitly configured loopback development origin.');
}
const config: Config = {
  title: 'Onesa AI', tagline: 'Engineering the shared intelligence platform',
  url:process.env.ONESA_DOCS_URL || `http://localhost:${internal ? 3201 : 3200}`, staticDirectories:[`.generated/${scope}/static`], baseUrl:'/', organizationName:'Onesa AI', projectName:'onesa-ai-platform',
  onBrokenLinks:'throw', trailingSlash:false,
  markdown:{format:'md', mermaid:true}, themes:['@docusaurus/theme-mermaid'],
  customFields:{documentationVersion:'0.2 · Amendment 002.2', apiUrl, scope, appUrl},
  presets:[['classic', {docs:{numberPrefixParser:false,path:`.generated/${scope}/docs`, sidebarPath:'./sidebars.ts', showLastUpdateTime:false}, pages:{path:`.generated/${scope}/pages`}, blog:false, theme:{customCss:'./src/css/custom.css'}} satisfies Options]],
  themeConfig:{
    colorMode:{defaultMode:'light', respectPrefersColorScheme:true},
    navbar:{title:'Onesa AI / Docs', items:[{to:internal?'/docs':'/docs/public/introduction',label:'Reference',position:'left'},{to:'/architecture',label:'Architecture',position:'left'},{to:'/api-explorer',label:'API',position:'left'},...(internal ? [{to:'/database',label:'Database',position:'left' as const}] : []),{to:'/tutorials',label:'Guides',position:'left'},{to:'/downloads',label:'Downloads',position:'left'},{to:'/assistant',label:'Ask Onesa',position:'left'},{label:'Onesa applications',position:'right',items:[{href:appUrl,label:'Onesa AI home'},{href:appUrl,label:'Onesa Chat'},{href:appUrl+'/knowledge',label:'Onesa Knowledge'},{href:appUrl+'/agents',label:'Onesa Agents'},{href:appUrl+'/travel',label:'Onesa Travel'}]},...(internal?[{href:process.env.ONESA_PUBLIC_DOCUMENTATION_URL||'http://localhost:3200',label:'Developer docs ↗',position:'right' as const}]:[]),{type:'search',position:'right'}]},
    footer:{style:'dark', copyright:'Onesa AI · European-based, globally applicable · Documentation v0.2'},
    prism:{additionalLanguages:['python','bash','json','sql','yaml','typescript']},
  } satisfies ThemeConfig,
};
export default config;
