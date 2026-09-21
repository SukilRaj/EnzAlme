export function LoadingState({ message = "Loading…" }) {
  return (
    <div className="state-panel">
      <div className="state-spinner" />
      <p>{message}</p>
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", message, onRetry }) {
  return (
    <div className="error-panel">
      <h3>{title}</h3>
      <p>{message}</p>
      {onRetry && (
        <button className="btn btn-ghost" onClick={onRetry} style={{ marginTop: 10 }}>
          Try again
        </button>
      )}
    </div>
  );
}
