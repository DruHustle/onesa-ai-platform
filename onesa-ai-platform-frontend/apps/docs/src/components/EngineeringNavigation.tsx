import {useEffect, useState} from 'react';

export type Topic = {id:string;title:string;diagram:string;url:string;summary:string};
export type Reference = {title:string;url:string};
export type LearningDay = {id:string;title:string;diagram:string;url:string;objectives:string[];checkpoints:string[];references:Reference[]};
export type EngineeringNavigation = {version:string;classification:'internal';reviewed_at:string;architecture:Topic[];chapters:Reference[];days:LearningDay[]};

export function useEngineeringNavigation(enabled:boolean) {
  const [navigation,setNavigation]=useState<EngineeringNavigation|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    if(!enabled)return;
    const abort=new AbortController();
    fetch('/generated/engineering-navigation.json',{signal:abort.signal})
      .then(async r=>{
        if(!r.ok||!r.headers.get('content-type')?.includes('application/json'))throw new Error('Engineering navigation is unavailable.');
        const value=await r.json();
        if(value.classification!=='internal'||!Array.isArray(value.architecture)||!Array.isArray(value.days))throw new Error('Engineering navigation is unavailable.');
        setNavigation(value);
      }).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return()=>abort.abort();
  },[enabled]);
  return {navigation,error};
}
