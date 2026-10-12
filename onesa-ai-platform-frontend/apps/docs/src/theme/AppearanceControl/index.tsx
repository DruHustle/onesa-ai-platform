import React,{useEffect,useState} from 'react';
import {useColorMode} from '@docusaurus/theme-common';
type Preference='auto'|'light'|'dark';
declare global {interface Window {OnesaAppearance?:{getPreference:()=>Preference;getMode:()=> 'light'|'dark';setPreference:(value:Preference)=>void;refresh:()=>void}}}
export default function AppearanceControl(){
 const {setColorMode}=useColorMode();
 const [preference,setPreference]=useState<Preference>('auto');
 useEffect(()=>{const update=()=>{const controller=window.OnesaAppearance;if(controller){setPreference(controller.getPreference());setColorMode(controller.getMode());}};update();window.addEventListener('onesa:appearance',update);return()=>window.removeEventListener('onesa:appearance',update);},[setColorMode]);
 return <label className="appearance-control navbar__item"><span>Appearance</span><select value={preference} title="Auto: light 07:00–18:59, dark 19:00–06:59 (local time)" onChange={event=>window.OnesaAppearance?.setPreference(event.target.value as Preference)}><option value="auto">Auto</option><option value="light">Light</option><option value="dark">Dark</option></select></label>;
}
