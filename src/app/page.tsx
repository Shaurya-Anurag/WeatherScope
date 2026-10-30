import Dashboard from './Dashboard';
import { loadDashboardData } from '../data';
export default async function Home() {
  const data = await loadDashboardData();
  return <Dashboard d={data} />;
}
