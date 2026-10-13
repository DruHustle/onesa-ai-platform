import {useEffect} from 'react';
import {useColorMode} from '@docusaurus/theme-common';
export default function AutomaticDayNight(){const {setColorMode}=useColorMode();useEffect(()=>{const update=()=>{const hour=new Date().getHours();setColorMode(hour>=19||hour<7?'dark':'light');};update();window.addEventListener('onesa:day-night',update);return()=>window.removeEventListener('onesa:day-night',update);},[setColorMode]);return null;}
