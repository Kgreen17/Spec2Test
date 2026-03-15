import React, {useState, useEffect, useRef} from 'react'
import axios from 'axios'

export default function Home(){
  const [file, setFile] = useState(null)
  const [url, setUrl] = useState('')
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [jobs, setJobs] = useState([])
  const pollingRef = useRef(null)

  const API_BASE = 'http://localhost:8000'

  const fetchJobs = async () => {
    try{
      const res = await axios.get(`${API_BASE}/api/jobs`)
      setJobs(res.data || [])
    }catch(e){
      console.warn('Failed to fetch jobs', e)
    }
  }

  useEffect(()=>{
    fetchJobs()
    // poll job list every 10s
    const id = setInterval(fetchJobs, 10000)
    return ()=> clearInterval(id)
  }, [])

  const pollStatus = async (jid) => {
    try{
      const res = await axios.get(`${API_BASE}/api/status/${jid}`)
      return res.data
    }catch(e){
      return null
    }
  }

  // start polling a specific job's status and refresh job list when it completes
  const watchJob = (jid) => {
    if(pollingRef.current) clearInterval(pollingRef.current)
    pollingRef.current = setInterval(async ()=>{
      const s = await pollStatus(jid)
      if(s){
        // update local displayed status
        setStatus(s.status)
        // refresh job list so new artifacts show up
        fetchJobs()
        if(['SUCCESS','COMPLETED','ERROR','FAIL'].includes((s.status || '').toUpperCase())){
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
      }
    }, 3000)
  }

  const submit = async (e) => {
    e.preventDefault()
    const form = new FormData()
    if(file) form.append('file', file)
    if(url) form.append('url', url)
    form.append('options', JSON.stringify({generate_tests: true, simulate_executor: true}))
    try{
      // use JSON path if file not present to avoid multipart requirement on server
      if(!file && url){
        const res = await axios.post(`${API_BASE}/api/upload`, {url, options: {generate_tests: true, simulate_executor: true}})
        setJobId(res.data.job_id)
        setStatus(res.data.status)
        watchJob(res.data.job_id)
      } else {
        const res = await axios.post(`${API_BASE}/api/upload`, form, { headers: {'Content-Type': 'multipart/form-data'} })
        setJobId(res.data.job_id)
        setStatus(res.data.status)
        watchJob(res.data.job_id)
      }
      // refresh jobs list
      fetchJobs()
    }catch(e){
      alert('Upload failed: ' + (e.response?.data?.detail || e.message))
    }
  }

  const openAllure = (job) => {
    // Try to open allure_report artifact if present, otherwise open allure-results folder
    const artifacts = job.artifacts || {}
    // artifact paths are like 'reports/job_<id>/allure-report' -> exposed under /artifacts/job_<id>/allure-report
    if(artifacts && artifacts.allure_report){
      // construct relative URL
      const parts = artifacts.allure_report.split('reports/')
      const rel = parts.length>1 ? parts[1] : artifacts.allure_report
      const url = `http://localhost:8000/artifacts/${rel}/index.html` // index.html inside allure-report
      window.open(url, '_blank')
      return
    }
    if(artifacts && artifacts.allure_results){
      const parts = artifacts.allure_results.split('reports/')
      const rel = parts.length>1 ? parts[1] : artifacts.allure_results
      const url = `http://localhost:8000/artifacts/${rel}`
      window.open(url, '_blank')
      return
    }
    alert('No allure artifact available yet for this job')
  }

  return (
    <div style={{padding:20}}>
      <h1>Spec2Test Dashboard (MVP)</h1>
      <form onSubmit={submit}>
        <div>
          <label>Upload file (PDF/DOCX/CSV):</label><br/>
          <input type="file" onChange={e=>setFile(e.target.files[0])} />
        </div>
        <div style={{marginTop:10}}>
          <label>or paste a URL (Confluence):</label><br/>
          <input type="text" style={{width:400}} value={url} onChange={e=>setUrl(e.target.value)} />
        </div>
        <div style={{marginTop:10}}>
          <button type="submit">Run Pipeline</button>
        </div>
      </form>

      {jobId && <div style={{marginTop:20}}>Job queued: {jobId} (status: {status})</div>}

      <h2 style={{marginTop:30}}>Recent Jobs</h2>
      <table style={{width:'100%', borderCollapse:'collapse'}}>
        <thead>
          <tr>
            <th style={{textAlign:'left', padding:6}}>Job ID</th>
            <th style={{textAlign:'left', padding:6}}>Status</th>
            <th style={{textAlign:'left', padding:6}}>Artifacts</th>
            <th style={{textAlign:'left', padding:6}}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.length===0 && <tr><td colSpan={4}>No jobs yet</td></tr>}
          {jobs.map((j)=>(
            <tr key={j.job_id} style={{borderTop:'1px solid #eee'}}>
              <td style={{padding:6}}>{j.job_id}</td>
              <td style={{padding:6}}>{j.status}</td>
              <td style={{padding:6}}>{Object.keys(j.artifacts||{}).join(', ')}</td>
              <td style={{padding:6}}>
                <button onClick={()=>watchJob(j.job_id)}>Watch</button>
                <button style={{marginLeft:8}} onClick={()=>openAllure(j)}>Open Allure</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

    </div>
  )
}
