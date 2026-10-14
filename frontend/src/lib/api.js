const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
async function request(path, options={}) {
  const res=await fetch(`${BASE}${path}`,options)
  const type=res.headers.get('content-type')||''
  if(!res.ok){let message=`Request failed (${res.status})`;try{const data=type.includes('json')?await res.json():await res.text();message=data.detail||data.message||message}catch{};throw new Error(message)}
  return type.includes('application/json')?res.json():res
}
export const api={
  health:()=>request('/api/health'), library:()=>request('/api/library'), analytics:()=>request('/api/analytics'), source:(id)=>request(`/api/library/${id}`),
  youtube:(url)=>request('/api/ingest/youtube',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})}),
  text:(title,content,source_type='notes')=>request('/api/ingest/text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,content,source_type})}),
  file:(file)=>{const fd=new FormData();fd.append('file',file);return request('/api/ingest/file',{method:'POST',body:fd})},
  summary:(id,length)=>request(`/api/sources/${id}/summary`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_id:id,length})}),
  notes:(id,style)=>request(`/api/sources/${id}/notes`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_id:id,style})}),
  chat:(source_id,question,history)=>request('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_id,question,history})}),
  quiz:(source_id,count,difficulty)=>request('/api/quiz',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_id,count,difficulty})}),
  flashcards:(source_id,count)=>request('/api/flashcards',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_id,count})}),
  interviewStart:(payload)=>request('/api/interview/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),
  interviewAnswer:(payload)=>request('/api/interview/answer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),
  interviewNext:(payload)=>request('/api/interview/next',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),
  deleteSource:(id)=>request(`/api/library/${id}`,{method:'DELETE'}),
  exportUrl:(id,format,kind)=>`${BASE}/api/sources/${id}/export?format=${format}&kind=${kind}`,
}
