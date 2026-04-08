import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Talent Audit Env',
  description: 'AI Agent Environment for HR Data Compliance',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
