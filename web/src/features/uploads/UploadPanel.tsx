import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { api, ApiError } from "../../lib/api";
import type { UploadedDocument } from "../../lib/types";
import { useIdentity } from "../../lib/identity-context";
import { Panel } from "../../components/primitives";

function StlPreview({ document }: { document: UploadedDocument }) {
  const mount = useRef<HTMLDivElement>(null); const { identity } = useIdentity();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const host = mount.current; if (!host) return;
    let disposed = false; const scene = new THREE.Scene(); scene.background = new THREE.Color(0x161a1f);
    const camera = new THREE.PerspectiveCamera(45, 16/9, .01, 10000); camera.position.set(2,2,2);
    const renderer = new THREE.WebGLRenderer({ antialias: true }); renderer.setSize(host.clientWidth, 300); host.appendChild(renderer.domElement);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x333344, 2)); const controls = new OrbitControls(camera, renderer.domElement);
    let frame = 0; const animate = () => { frame=requestAnimationFrame(animate); controls.update(); renderer.render(scene,camera); }; animate();
    api.documentContent(document.document_id, identity).then(buffer => {
      if (disposed) return; const geometry=new STLLoader().parse(buffer); geometry.center(); geometry.computeBoundingSphere();
      const radius=geometry.boundingSphere?.radius || 1; camera.position.set(radius*2,radius*1.4,radius*2); camera.near=Math.max(radius/1000,.001); camera.far=radius*100; camera.updateProjectionMatrix();
      scene.add(new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x4fa3d1,roughness:.55,metalness:.2})));
    }).catch(e => setError(e instanceof Error ? e.message : "Preview unavailable"));
    return () => { disposed=true; cancelAnimationFrame(frame); controls.dispose(); renderer.dispose(); host.replaceChildren(); };
  }, [document.document_id, identity]);
  return <div>{error && <p className="upload-error">{error}</p>}<div className="model-preview" ref={mount} aria-label={`3D preview of ${document.filename}`} /></div>;
}

export function UploadPanel() {
  const { identity }=useIdentity(); const [documents,setDocuments]=useState<UploadedDocument[]>([]);
  const [file,setFile]=useState<File|null>(null); const [busy,setBusy]=useState(false); const [error,setError]=useState<string|null>(null);
  const refresh=useCallback(()=>api.listDocuments(identity).then(r=>setDocuments(r.documents)).catch(e=>setError(e instanceof ApiError?e.message:"Could not load uploads.")),[identity]);
  useEffect(()=>{ void refresh(); },[refresh]);
  useEffect(()=>{ if (!documents.some(d=>d.state==="received"||d.state==="processing")) return; const timer=setInterval(refresh,1200); return()=>clearInterval(timer); },[documents,refresh]);
  async function upload(){ if(!file)return; setBusy(true);setError(null);try{await api.uploadDocument(file,identity);setFile(null);await refresh();}catch(e){setError(e instanceof ApiError?e.message:"Upload failed.");}finally{setBusy(false)}}
  return <div className="upload-layout"><Panel title="Upload governed content" description="PDF, STL, or STEP · 50 MiB default · access is limited to your current dev role/site.">
    <div className="upload-controls"><input aria-label="Document file" type="file" accept=".pdf,.stl,.step,.stp" onChange={e=>setFile(e.target.files?.[0]||null)}/><button className="btn btn-primary" disabled={!file||busy} onClick={upload}>{busy?"Uploading…":"Upload & process"}</button></div>
    {error&&<p className="upload-error">{error}</p>}</Panel>
    <Panel title="Processing status" description="Originals are retained before extraction starts. Refresh/polling exposes each state.">
      {!documents.length&&<p className="empty-state">No authorized uploads yet.</p>}
      <div className="upload-list">{documents.map(d=><article className="upload-card" key={d.document_id}><div><strong>{d.filename}</strong><span className={`state state-${d.state}`}>{d.state.replaceAll("_"," ")}</span></div><small>{d.format} · {(d.size_bytes/1024).toFixed(1)} KiB · {d.document_id}</small>{d.message&&<p>{d.message}</p>}
      {d.state.startsWith("completed")&&d.format==="STL"&&<StlPreview document={d}/>} {d.format==="STEP"&&<div className="step-fallback"><strong>STEP representation</strong><pre>{JSON.stringify(d.metadata,null,2)}</pre><span>Interactive B-rep preview is optional; metadata and extracted geometry remain searchable.</span></div>}</article>)}</div>
    </Panel></div>;
}
