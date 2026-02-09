import React, { useEffect, useState } from 'react';
import Stomp from 'stompjs';
import { useAuth } from '@/contexts/AuthContext';

const SocketTest = () => {
  const [receivedMessage, setReceivedMessage] = useState("아직 메시지 없음");
  const [stompClient, setStompClient] = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws';
    const socket = new WebSocket(wsUrl);
    const client = Stomp.over(socket);

    // 2. 연결 시도
    client.connect({}, (frame) => {
      console.log('✅ 웹소켓 연결 성공!', frame);

      const userId = user?.id || 1;

      // 3. 구독 (서버가 보내는 메시지 듣기)
      client.subscribe(`/sub/${userId}/test`, (response) => {
        console.log('📩 서버에서 온 메시지:', response.body);
        setReceivedMessage(response.body);
      });
      
      setStompClient(client);
    }, (error) => {
      console.error('❌ 웹소켓 연결 실패:', error);
    });

    // 컴포넌트 언마운트 시 연결 종료
    return () => {
      if (client) client.disconnect();
    };
  }, [user]);

  const sendMessage = () => {
    if (stompClient && user?.id) {
      const payload = {
        userId: user.id,
        content: "Hello Robot!"
      };
      // 4. 메시지 전송 (발행)
      stompClient.send("/pub/test", {}, JSON.stringify(payload));
      console.log('📤 메시지 보냄:', payload);
    } else {
      console.log('📤 메시지 보냄:', payload);
    }
  };

  return (
    <div className="p-4 bg-gray-100 rounded-lg border border-gray-300 m-4">
      <h3 className="font-bold text-lg mb-2">📡 웹소켓 테스트</h3>
      <p className="mb-2">서버 응답: <span className="text-blue-600 font-bold">{receivedMessage}</span></p>
      <button 
        onClick={sendMessage}
        className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
      >
        테스트 메시지 보내기
      </button>
    </div>
  );
};

export default SocketTest;