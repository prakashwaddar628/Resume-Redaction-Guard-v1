"use client";

import React from "react";
import styles from "./ResumeCard.module.css";

interface RecordObj {
  record_id: string;
  raw: Record<string, any>;
  source_file: string;
}

interface ResumeCardProps {
  record: RecordObj;
  category?: string;
  risk?: string;
}

export default function ResumeCard({ record, category, risk }: ResumeCardProps) {
  const isRedacted = (val: string) => val === "[REDACTED]";

  const piiFields = ["name", "email", "phone", "address"];
  
  const skills = record.raw.skills || [];

  return (
    <div className={`${styles.card} glass-panel animate-fade-in`}>
      <div className={styles.header}>
        <div className={styles.recordId}>
          {record.source_file} <span style={{color: "#555"}}>({record.record_id})</span>
        </div>
        <div className={styles.status}>
          {category && (
            <span className={styles.categoryTag}>{category}</span>
          )}
          {risk && (
            <span className={`${styles.categoryTag} ${risk === "High" ? styles.riskHigh : styles.riskLow}`}>
              Risk: {risk}
            </span>
          )}
        </div>
      </div>

      <div className={styles.piiGrid}>
        {piiFields.map((field) => {
          if (record.raw[field] === undefined) return null;
          const val = record.raw[field];
          const redacted = isRedacted(val);
          return (
            <div key={field} className={styles.field}>
              <div className={styles.fieldLabel}>{field}</div>
              <div className={`${styles.fieldValue} ${redacted ? styles.redacted : ""}`}>
                {val}
              </div>
            </div>
          );
        })}
      </div>

      <div className={styles.techSection}>
        <div className={styles.techHeader}>Technical Skills</div>
        <div className={styles.skillList}>
          {Array.isArray(skills) ? (
            skills.map((skill, i) => (
              <span key={i} className={styles.skillBadge}>{skill}</span>
            ))
          ) : (
            <span className={styles.skillBadge}>{skills}</span>
          )}
        </div>
      </div>
    </div>
  );
}
