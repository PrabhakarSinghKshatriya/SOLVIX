import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [backend, setBackend] = useState("Checking...");
  const [database, setDatabase] = useState("Checking...");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => response.json())
      .then((data) => {
        setBackend(data.status);
        setDatabase(data.database);
      })
      .catch(() => {
        setBackend("offline");
        setDatabase("unknown");
      });
  }, []);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#f5f7fb",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div
        style={{
          width: "90%",
          maxWidth: "700px",
          background: "white",
          padding: "45px",
          borderRadius: "24px",
          boxShadow: "0 15px 50px rgba(0,0,0,0.08)",
          textAlign: "center",
        }}
      >
        <h1 style={{ fontSize: "52px", margin: 0 }}>
          SOLVIX
        </h1>

        <p style={{ color: "#666", fontSize: "19px" }}>
          Connect. Solve. Get It Done.
        </p>

        <div style={{ marginTop: "40px" }}>
          <p>
            Backend:{" "}
            <strong>{backend}</strong>
          </p>

          <p>
            Database:{" "}
            <strong>{database}</strong>
          </p>
        </div>

        <div
          style={{
            marginTop: "30px",
            padding: "18px",
            borderRadius: "12px",
            background: "#ecfdf5",
          }}
        >
          🚀 SOLVIX Foundation is running
        </div>
      </div>
    </div>
  );
}

export default App;