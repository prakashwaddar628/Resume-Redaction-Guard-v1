"use client";

import React, { useEffect, useRef } from "react";
import styles from "./AgentConsole.module.css";

interface LogEntry {
  step: number;
  action_type: string;
  reward: number;
  feedback: string;
}

interface AgentConsoleProps {
  logs: LogEntry[];
  totalReward: number;
}

export default function AgentConsole({ logs, totalReward }: AgentConsoleProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className={`${styles.console} glass-panel`}>
      <div className={styles.header}>
        <div className={styles.title}>
          <div className={styles.dot}></div>
          Agent System Console
        </div>
        <div className={styles.stats}>
          Reward: {totalReward > 0 ? "+" : ""}{totalReward.toFixed(2)}
        </div>
      </div>
      
      <div className={styles.logs} ref={scrollRef}>
        {logs.length === 0 ? (
          <div style={{ color: "#555", fontStyle: "italic", textAlign: "center", marginTop: "2rem" }}>
            Waiting for agent actions...
          </div>
        ) : (
          logs.map((log, i) => (
            <div 
              key={i} 
              className={styles.logEntry}
              style={{
                borderLeftColor: log.reward > 0 ? 'var(--accent-green)' : (log.reward < 0 ? 'var(--accent-red)' : '#888')
              }}
            >
              <div className={styles.logHeader}>
                <span>Step {log.step.toString().padStart(2, '0')}</span>
                <span className={styles.logAction}>[{log.action_type}]</span>
                <span className={`
                  ${styles.logReward} 
                  ${log.reward > 0 ? styles.rewardPos : (log.reward < 0 ? styles.rewardNeg : styles.rewardZero)}
                `}>
                  {log.reward > 0 ? "+" : ""}{log.reward.toFixed(2)}
                </span>
              </div>
              <div className={styles.logFeedback}>{log.feedback}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
