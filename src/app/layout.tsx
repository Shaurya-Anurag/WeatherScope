import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'WeatherScope | Global Weather Intelligence', description: 'Local-first global weather analytics, anomaly detection and forecasting.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
