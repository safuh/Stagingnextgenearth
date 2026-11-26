"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, apiPost, clearSession } from "@/lib/api";
type Org={id:string;name:string};
type Programme={id:string;title:string;status:string;organization_id:string};
type Application={id:string;programme_id:string;programme_title:string|null;user_id:string;applicant_identifier:string|null;participation_type:string;interest:string;availability:string|null;status:string;review_note:string|null;reviewed_by:string|null;reviewed_at:string|null;safeguarding_confirmed:boolean};
export default function VolunteerApplicationsPage(){
 const [orgs,setOrgs]=useState<Org[]>([]),[orgId,setOrgId]=useState("");
 const [programmes,setProgrammes]=useState<Programme[]>([]),[applications,setApplications]=useState<Application[]>([]);
 const [confirmed,setConfirmed]=useState<Record<string,boolean>>({});
 const [error,setError]=useState(""),[notice,setNotice]=useState(""),[busy,setBusy]=useState(false);
 async function load(id:string){
  const items=await apiGet<Programme[]>("/organizations/"+id+"/programmes");setProgrammes(items);
  const queue=await apiGet<Application[]>("/organizations/"+id+"/volunteer-applications");
  setApplications(queue);
 }
 useEffect(()=>{apiGet<Org[]>("/organizations").then(items=>{setOrgs(items);if(items[0])setOrgId(items[0].id);}).catch(e=>setError(e instanceof Error?e.message:"Unable to load organisations."));},[]);
 useEffect(()=>{if(orgId)load(orgId).catch(e=>setError(e instanceof Error?e.message:"Unable to load applications."));},[orgId]);
 async function decide(item:Application,decision:"approved"|"rejected"){
  if(decision==="approved"&&!confirmed[item.id]){setError("Confirm safeguarding checks and any required guardian consent before approval.");return;}
  setBusy(true);setError("");setNotice("");
  try{
   await apiPost("/organizations/"+orgId+"/programmes/"+item.programme_id+"/volunteer-applications/"+item.id+"/decision",{decision,safeguarding_verified:decision==="approved"&&Boolean(confirmed[item.id])});
   await load(orgId);setNotice(decision==="approved"?"Applicant approved and youth-volunteer membership activated.":"Application rejected.");
  }catch(e){setError(e instanceof Error?e.message:"Unable to process application.");}finally{setBusy(false);}
 }
 const pending=applications.filter(item=>item.status==="pending");
 return <main className="workspace-shell"><header className="workspace-topbar"><Link className="brand" href="/workspace">NextGen For Earth</Link><button className="workspace-signout" onClick={()=>{clearSession();window.location.assign("/");}}>Sign out</button></header><section className="workspace-content"><p className="eyebrow">PEOPLE & SAFEGUARDING</p><h1 className="workspace-title">Volunteer <em>applications.</em></h1><p className="workspace-muted">Review programme applications. Approval activates a youth-volunteer membership. Confirm required safeguarding and guardian-consent checks before approval.</p><p><Link className="secondary-action" href="/workspace/administration">← Administration</Link></p>{orgs.length>1&&<label>Organisation<select value={orgId} onChange={e=>setOrgId(e.target.value)}>{orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label>}{error&&<p className="workspace-error" role="alert">{error}</p>}{notice&&<p className="workspace-notice" role="status">{notice}</p>}<section className="staff-card admin-member-section"><h2>Pending applications ({pending.length})</h2>{pending.length===0&&<p className="workspace-muted">There are no pending applications.</p>}{pending.map(item=><article className="admin-member-row" key={item.id}><div className="admin-member-meta"><strong>{item.applicant_identifier??("Applicant "+item.user_id.slice(0,8))}</strong><span>{item.programme_title??programmes.find(p=>p.id===item.programme_id)?.title??"Programme"} · {item.participation_type}</span><p>{item.interest}</p>{item.availability&&<span>Availability: {item.availability}</span>}</div><div className="admin-member-actions"><label><input type="checkbox" checked={Boolean(confirmed[item.id])} onChange={e=>setConfirmed(old=>({...old,[item.id]:e.target.checked}))}/> Safeguarding and any required guardian consent verified</label><button className="primary-action" disabled={busy||!confirmed[item.id]} onClick={()=>void decide(item,"approved")}>Approve applicant</button><button className="secondary-action" disabled={busy} onClick={()=>void decide(item,"rejected")}>Reject</button></div></article>)}</section><section className="staff-card admin-member-section"><h2>Programme applications overview</h2>{programmes.map(p=><p key={p.id}>{p.title} · {p.status} · {applications.filter(a=>a.programme_id===p.id).length} applications</p>)}</section><section className="staff-card admin-member-section"><h2>Decision history ({applications.filter(item=>item.status!=="pending").length})</h2>{applications.filter(item=>item.status!=="pending").length===0?<p className="workspace-muted">Reviewed applications will appear here.</p>:applications.filter(item=>item.status!=="pending").map(item=><article className="admin-member-row" key={item.id}><div className="admin-member-meta"><strong>{item.applicant_identifier??("Applicant "+item.user_id.slice(0,8))}</strong><span>{item.programme_title??programmes.find(p=>p.id===item.programme_id)?.title??"Programme"} · {item.participation_type} · {item.status}</span>{item.reviewed_at&&<small>Reviewed {new Date(item.reviewed_at).toLocaleString()}{item.reviewed_by?" · Reviewer "+item.reviewed_by:""}</small>}{item.review_note&&<p>{item.review_note}</p>}{item.safeguarding_confirmed&&<small>Safeguarding verification recorded</small>}</div></article>)}</section></section></main>;
}
