import { Link } from "react-router-dom";

export function Privacy() {
  return (
    <div className="min-h-dvh w-full font-sans bg-[#F9F9F8] bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:16px_16px] px-6 py-12 md:py-20 text-ink">
      <div className="w-full max-w-[680px] mx-auto">
        <Link to="/login" className="text-sm text-ink-muted hover:text-ink transition-colors mb-12 inline-block">
          &larr; Back to login
        </Link>
        <h1 className="font-['Georgia','Times_New_Roman',serif] text-3xl md:text-4xl font-medium mb-6">Privacy Policy</h1>
        <p className="text-sm text-ink-muted mb-8">Last updated: September 2026</p>
        
        <div className="text-ink text-base leading-relaxed space-y-6">
          <p>
            PRISM is an independent engineering project built to demonstrate research-paper claim auditing. It is not a commercial product, and this policy describes how it currently handles data — not a company's data-handling promises.
          </p>

          <h2 className="font-['Georgia','Times_New_Roman',serif] text-xl font-medium mt-10 mb-4">What PRISM collects</h2>
          <ul className="list-disc pl-5 space-y-3">
            <li><strong>Papers you upload.</strong> PDF content is processed to extract claims and evidence spans. Uploaded files and extracted data are stored in the project's database and vector index to power the audit and chat features.</li>
            <li><strong>Account information, if you sign in with Google.</strong> PRISM receives your name, email address, and profile identifier from Google's sign-in flow. No other Google account data is requested or accessed.</li>
            <li><strong>Guest sessions.</strong> If you continue as a guest, no account information is collected. Usage during a guest session is tied to a temporary session identifier, not to you personally.</li>
            <li><strong>Standard technical logs.</strong> Request timestamps, error traces, and performance metrics are recorded for debugging, the same as any hosted web application.</li>
          </ul>

          <h2 className="font-['Georgia','Times_New_Roman',serif] text-xl font-medium mt-10 mb-4">What PRISM does not do</h2>
          <ul className="list-disc pl-5 space-y-3">
            <li>PRISM does not sell, rent, or share your data with third parties.</li>
            <li>PRISM does not use uploaded papers or account data for any purpose beyond running the audit and chat features you request.</li>
            <li>PRISM does not run advertising or third-party tracking.</li>
          </ul>

          <h2 className="font-['Georgia','Times_New_Roman',serif] text-xl font-medium mt-10 mb-4">Where data is processed</h2>
          <p>
            Extraction and audit calls are sent to third-party LLM providers (currently Google Gemini and Groq) to generate claim and evidence analysis. Only the paper content necessary for that specific request is sent. Refer to those providers' own privacy policies for how they handle API-submitted content.
          </p>

          <h2 className="font-['Georgia','Times_New_Roman',serif] text-xl font-medium mt-10 mb-4">Data retention and deletion</h2>
          <p>
            Because this is a demo project, uploaded papers and account data may be deleted at any time as the project is developed or reset, without notice. If you would like your data removed sooner, email the address below.
          </p>

          <h2 className="font-['Georgia','Times_New_Roman',serif] text-xl font-medium mt-10 mb-4">Your options</h2>
          <ul className="list-disc pl-5 space-y-3">
            <li>Do not upload any paper you would not want processed by third-party LLM providers, or that contains confidential or sensitive material.</li>
            <li>Use guest access if you would prefer not to share Google account information.</li>
          </ul>

          <h2 className="font-['Georgia','Times_New_Roman',serif] text-xl font-medium mt-10 mb-4">Contact</h2>
          <p>
            Questions or deletion requests: nitin8764@live.com
          </p>
        </div>
      </div>
    </div>
  );
}
