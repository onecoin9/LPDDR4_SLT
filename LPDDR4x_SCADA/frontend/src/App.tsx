import { Routes, Route } from 'react-router'
import Home from './pages/Home'
import ManualDebug from './pages/ManualDebug'
import LicenseNotice from './sections/LicenseNotice'

export default function App() {
  return (
    <><LicenseNotice /><Routes>
      <Route path="/" element={<Home />} />
      <Route path="/manual" element={<ManualDebug />} />
    </Routes></>
  )
}
