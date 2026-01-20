import React, { useRef } from 'react'; // useRef 추가
import { Joystick } from 'react-joystick-component';
import { useRobot } from '../contexts/RobotContext'; // ✅ Context 가져오기

const ControlPanel = () => {
  // ✅ RobotContext에서 moveRobot 함수 가져오기
  const { moveRobot } = useRobot();
  
  // ⚡ 전송 속도 제한용 (너무 많은 데이터 전송 방지)
  const lastSentTime = useRef(0);

  const handleMove = (event) => {
    // 1. 0.1초(100ms) 간격으로만 전송 (서버 과부하 방지)
    const now = Date.now();
    if (now - lastSentTime.current < 100) return;
    lastSentTime.current = now;

    // 2. 조이스틱 데이터 변환
    // event.y: 앞(+), 뒤(-) / event.x: 우(+), 좌(-)
    // 로봇마다 회전 방향이 다를 수 있으니 움직여보고 - 부호를 조정하세요.
    const linear = event.y || 0;
    const angular = -event.x || 0; // 좌우 반전 필요 시 - 붙임

    // 3. 웹소켓으로 전송 (axios 대신 사용!)
    moveRobot(linear, angular);
    
    // 로그는 너무 많이 찍히니 개발할 때만 주석 해제
    // console.log(`🚀 Move: Linear=${linear.toFixed(2)}, Angular=${angular.toFixed(2)}`);
  };

  const handleStop = () => {
    // 멈출 때는 즉시 전송
    moveRobot(0, 0);
    console.log("🛑 Stop command sent");
  };

  return (
    <div style={styles.card}>
      <h3>🕹️ Manual Control</h3>
      <div style={styles.joystickWrapper}>
        <Joystick 
          size={120} 
          sticky={false} 
          baseColor="#444" 
          stickColor="#888" 
          move={handleMove} 
          stop={handleStop}
          throttle={100} // 라이브러리 자체 스로틀링 옵션도 활용
        />
      </div>
      <p style={{fontSize: '0.8rem', color: '#aaa', marginTop: '10px'}}>
        Use joystick to move robot
      </p>
    </div>
  );
};

const styles = {
  card: {
    backgroundColor: '#333',
    padding: '20px',
    borderRadius: '12px',
    boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    width: '100%',
    maxWidth: '400px',
    color: 'white', // 글자색 추가
  },
  joystickWrapper: {
    marginTop: '10px',
    padding: '10px',
    background: '#222',
    borderRadius: '50%'
  }
};

export default ControlPanel;