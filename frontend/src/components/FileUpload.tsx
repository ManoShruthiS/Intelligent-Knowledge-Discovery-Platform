import { useState } from 'react'
import api from '../services/api'
import { CloudUpload } from 'lucide-react'

export default function FileUpload({ onDone }: { onDone: (docId:string, name:string)=>void }) {
  const [file, setFile] = useState<File|null>(null)
  const [progress, setProgress] = useState(0)

  const handleDrop = (e:React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f && f.type === 'application/pdf') setFile(f)
  }

  const upload = async () => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const resp = await api.post('/upload', form, {
      onUploadProgress: (ev) => setProgress(Math.round((ev.loaded/ev.total)*100))
    })
    onDone(resp.data.doc_id, file.name)
  }

  return (
    <div
      className="border-2 border-dashed border-gray-300 p-8 text-center rounded-lg hover:bg-gray-50"
      onDrop={handleDrop}
      onDragOver={(e)=>e.preventDefault()}
    >
      <CloudUpload size={48} className="mx-auto mb-4 text-primary"/>
      <p className="mb-2">Drag & drop a PDF here or click to browse</p>
      <input type="file" accept="application/pdf" onChange={e=>e.target.files && setFile(e.target.files[0])}/>
      {file && (
        <div className="mt-4">
          <p>{file.name} – {(file.size/1024/1024).toFixed(2)} MB</p>
          <button
            className="mt-2 px-4 py-2 bg-primary text-white rounded"
            onClick={upload}
          >Upload</button>
          {progress>0 && <p>{progress}%</p>}
        </div>
      )}
    </div>
  )
}
