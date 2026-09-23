import { App as AntApp, Layout } from 'antd';

import Dashboard from './pages/Dashboard';

export default function App() {
  return (
    <AntApp>
      <Layout style={{ minHeight: '100%', background: 'transparent' }}>
        <Dashboard />
      </Layout>
    </AntApp>
  );
}
