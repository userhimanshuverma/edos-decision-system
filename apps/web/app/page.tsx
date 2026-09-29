export default function Home() {
  return (
    <main className="shell-container">
      <div className="shell-card">
        <div className="badge-row">
          <span className="badge">Foundation phase</span>
          <span className="badge badge-muted">Day 1</span>
        </div>

        <h1 className="shell-title">EDOS</h1>
        <h2 className="shell-subtitle">
          Enterprise Decision Operating System
        </h2>

        <p className="shell-description">
          Decision intelligence for operational systems.
        </p>

        <div className="status-footer">
          <span className="status-indicator">
            <span className="status-dot"></span>
            Operational Foundation Active
          </span>
          <span>Next.js + TypeScript</span>
        </div>
      </div>
    </main>
  );
}
