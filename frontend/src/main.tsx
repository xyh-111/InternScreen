import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#2563eb',
          colorBgBase: '#ffffff',
          borderRadius: 10,
          fontSize: 14,
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);
