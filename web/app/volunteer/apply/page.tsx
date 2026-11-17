"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost, restoreSession } from "@/lib/api";
type Programme={id:string;organization_id:string;title:string;slug:string;summary:string|null;status:string};
export default function VolunteerApplyPage(){
 const [programmes,setProgrammes]=useState<Programme[]>([]);
 const [selected,setSelected]=useState("");
 const [signedIn,setSignedIn]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 useEffect(()=>{
  let active=true;
  restoreSession().then(session=>{if(active)setSignedIn(Boolean(session));}).catch(()=>{if(active)setSignedIn(false);});
  apiGet<Programme[]>("/public/organizations/nextgen-for-earth/programmes")
   .then(items=>{setProgrammes(items);if(items[0])setSelected(items[0].id);})
   .catch(e=>setError(e instanceof Error?e.message:"Unable to load current programmes."));
  return ()=>{active=false;};
 },[]);
 async function submit(e:FormEvent<HTMLFormElement>){
  e.preventDefault();const form=e.currentTarget,data=new FormData(form);
  const programme=programmes.find(p=>p.id===selected);if(!programme){setError("Choose an available programme.");return;}
  if(!signedIn){setError("Sign in or create an account before submitting an application.");return;}
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiPost<{id:string;status:string}>("/organizations/"+programme.organization_id+"/programmes/"+programme.id+"/volunteer-applications",{
    participation_type:String(data.get("participation_type")||"volunteer"),
    interest:String(data.get("interest")||"").trim(),
    availability:String(data.get("availability")||"").trim()||null,
   });
   setNotice("Your application has been received. Status: "+result.status+".");
   form.reset();
  }catch(x){setError(x instanceof Error?x.message:"Unable to submit your application.");}
  finally{setBusy(false);}
 }
 return <main className="workspace-shell"><header className="workspace-topbar"><Link className="brand" href="/">NextGen For Earth</Link><Link className="secondary-action" href="/learners">Learner account access</Link></header><section className="workspace-content"><p className="eyebrow">GET INVOLVED</p><h1 className="workspace-title">Volunteer with <em>NextGen.</em></h1><p className="workspace-muted">Explore active programmes and submit an expression of interest. Programme teams review every application before membership is activated.</p>{error&&<p className="workspace-error" role="alert">{error}</p>}{notice&&<p className="workspace-notice" role="status">{notice}</p>}{programmes.length===0?<section className="staff-card"><h2>No open applications</h2><p>There are no programmes currently accepting volunteer applications. Please check again later.</p></section>:<section className="staff-card"><form onSubmit={submit}><label>Programme<select value={selected} onChange={e=>setSelected(e.target.value)}>{programmes.map(p=><option key={p.id} value={p.id}>{p.title}</option>)}</select></label>{programmes.find(p=>p.id===selected)?.summary&&<p>{programmes.find(p=>p.id===selected)?.summary}</p>}<label>How would you like to participate?<select name="participation_type"><option value="volunteer">Volunteer</option><option value="ambassador">Ambassador</option></select></label><label>Why are you interested? <textarea name="interest" rows={5} minLength={20} maxLength={5000} required placeholder="Describe your interests and relevant experience. Do not include sensitive personal information."/></label><label>Availability (optional)<input name="availability" maxLength={500} placeholder="For example, weekends or school holidays"/></label><p className="workspace-muted">A portal account is required. Do not include private contact, health or other sensitive information in your application. If you are under 18, a parent or guardian must provide any consent required by the programme before participation.</p>{!signedIn&&<p><Link href="/learners">Create or access your learner account</Link> before submitting.</p>}<button className="primary-action" disabled={busy||!signedIn}>{busy?"Submitting…":"Submit expression of interest"}</button></form></section>}<p><Link href="/">Return to the main website</Link></p></section></main>;
}
