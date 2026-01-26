import React from 'react';
import { useRobot } from '../contexts/RobotContext';

const ConnectionStatus = () => {
  const { isConnected } = useRobot();

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '8px 12px',
      backgroundColor: 'white',
      borderRadius: '20px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      fontWeight: 'bold',
      fontSize: '0.9rem',
    }}>
      {/* 상태 표시등 (동그라미) */}
      <div style={{
        width: '12px',
        height: '12px',
        borderRadius: '50%',
        backgroundColor: isConnected ? '#4CAF50' : '#F44336', // 초록 vs 빨강
        boxShadow: isConnected ? '0 0 8px #4CAF50' : 'none',
        transition: 'all 0.3s ease'
      }} />
      
      {/* 텍스트 */}
      <span style={{ color: isConnected ? '#2E7D32' : '#C62828' }}>
        {isConnected ? '시스템 정상 (Online)' : '연결 끊김 (Offline)'}
      </span>
    </div>
  );
};

export default ConnectionStatus;