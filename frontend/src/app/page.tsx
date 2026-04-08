"use client";

import { useState, useEffect } from "react";
import styles from "./page.module.css";
import ResumeCard from "../components/ResumeCard";
import AgentConsole from "../components/AgentConsole";

export default function Home() {
  const [activeTask, setActiveTask] = useState<string>("pii_easy");
  const [stateData, setStateData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [agentRunning, setAgentRunning] = useState(false);

  const API_URL = "http://localhost:8000";

  const fetchState = async () => {
    try {
      const res = await fetch(`${API_URL}/state`);
      const data = await res.json();
      setStateData(data);
    } catch (e) {
      console.error("Error fetching state:", e);
    }
  };

  const startTask = async (taskId: string) => {
    setLoading(true);
    setActiveTask(taskId);
    setAgentRunning(false);
    try {
      await fetch(`${API_URL}/reset?task_id=${taskId}`, { method: "POST" });
      await fetchState();
    } catch (e) {
      console.error("Failed to reset env", e);
    }
    setLoading(false);
  };

  // On mount, fetch the current state
  useEffect(() => {
    fetchState();
  }, []);

  const runAgentStep = async (taskId: string) => {
    if (!stateData || stateData.done) return;
    
    // Simple mock logic for the agent for demo purposes natively triggering the endpoint
    // In reality the CLI runner or Python loop calls the step API.
    // We will just fetch state continuously if it's running via Python, 
    // OR mock it by sending a predefined backend API call. 
    // Wait, the backend doesn't have an "agent.act" integrated, the agent drives it.
    // For visual effects, we can just fetch the state every 1s if we trigger a Python script,
    // but the python script isn't an API. 
    // So we'll just poll the state and display it!
  };

  // Polling mechanism
  useEffect(() => {
    if (agentRunning) {
      const interval = setInterval(fetchState, 500);
      return () => clearInterval(interval);
    }
  }, [agentRunning]);

  const tasks = [
    { id: "pii_easy", title: "Easy", desc: "Redact phone number from a single record." },
    { id: "pii_medium", title: "Medium", desc: "Categorize and redact PII for 5 records." },
    { id: "audit_hard", title: "Hard", desc: "Detect cross-record conflicts and flag High-Risk profiles." },
  ];

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.title}>Talent Audit Env</h1>
        <p className={styles.subtitle}>
          Automated HR Data Compliance AI. Watch the agent sanitize PII, categorize technical skills, and flag risks in real-time.
        </p>
      </header>

      <div className={styles.dashboard}>
        <div className={styles.leftCol}>
          
          <div className={`${styles.taskSelector} glass-panel`}>
            <h2>Select Task</h2>
            <div className={styles.taskGrid}>
              {tasks.map(t => (
                <div 
                  key={t.id} 
                  className={`${styles.taskCard} ${activeTask === t.id ? (t.id === "pii_easy" ? styles.activeEasy : t.id === "pii_medium" ? styles.activeMedium : styles.activeHard) : ""}`}
                  onClick={() => startTask(t.id)}
                >
                  <div className={styles.taskTitle}>{t.title}</div>
                  <div className={styles.taskDesc}>{t.desc}</div>
                </div>
              ))}
            </div>

            <div className={styles.actionArea}>
              <button 
                className={styles.primaryBtn} 
                onClick={() => setAgentRunning(!agentRunning)}
                disabled={loading}
              >
                {agentRunning ? "Stop Live Poll" : "Live Agent Poll"}
              </button>
              <span style={{color: "#888", fontSize: "0.8rem"}}>
                (Run `python run_demo.py --task {activeTask}` in terminal while polling)
              </span>
            </div>
          </div>

          <div className={styles.recordsList}>
            {stateData && stateData.records ? (
              Object.keys(stateData.records).map(rid => {
                const rec = {
                  record_id: rid,
                  raw: stateData.records[rid],
                  source_file: "resume.json" // simplified
                };
                return (
                  <ResumeCard 
                    key={rid} 
                    record={rec} 
                    category={stateData.categorized?.[rid]}
                    risk={stateData.flagged?.[rid]}
                  />
                );
              })
            ) : (
              <div style={{color: "#888", padding: "2rem", textAlign: "center"}}>No records loaded. Select a task.</div>
            )}
          </div>
        </div>

        <div className={styles.rightCol}>
          <div className={styles.consoleArea}>
            <AgentConsole 
              logs={stateData?.history || []} 
              totalReward={stateData?.total_reward || 0} 
            />
          </div>
        </div>
      </div>
    </main>
  );
}
