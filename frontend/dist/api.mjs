export const routes = {me:'/v1/auth/me',login:'/v1/auth/login',logout:'/v1/auth/logout',bootstrap:'/v1/auth/bootstrap',
  bootstrapStatus:'/v1/auth/bootstrap-status',overview:'/v1/overview',incidents:'/v1/incidents',events:'/v1/events',
  runs:'/v1/ai/runs',analyze:'/v1/ai/analyze',actions:'/v1/actions',playbooks:'/v1/playbooks',assets:'/v1/assets',
  integrations:'/v1/integrations',audit:'/v1/audit',users:'/v1/users',settings:'/v1/settings',health:'/health',
  demo:'/v1/demo',ingestEvents:'/v1/ingest/events',ingestIncidents:'/v1/ingest/incidents'};
export function escapeHTML(v){return String(v??'UNKNOWN').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
export function can(role,action){return ({investigate:['analyst'],propose:['analyst'],approve:['operator'],execute:['operator'],rollback:['operator'],manage:['admin']})[action]?.includes(role)??false;}
export function actionLabel(action){return action.dry_run?'DRY RUN · Simulation — no firewall or endpoint changed.':'LIVE · Confirmed only after successful state verification.';}
export async function api(path,{method='GET',body}={}){
  const csrf = document.cookie.split('; ').find(v=>v.startsWith('sz_csrf='))?.split('=')[1]??'';
  const response=await fetch(path,{method,credentials:'same-origin',cache:'no-store',redirect:'error',
    headers:{'Content-Type':'application/json',...(method!=='GET'?{'X-CSRF-Token':decodeURIComponent(csrf)}:{})},
    ...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await response.json();
  if(!response.ok){const error=Error(data.detail?.code??`Request failed (${response.status})`);error.status=response.status;throw error;}
  return data;
}
