import React, { useRef } from 'react';
import { Joystick } from 'react-joystick-component';
import { useRobot } from '../contexts/RobotContext'; // 경로 확인 필요
import { Gamepad2 } from 'lucide-react'; // 아이콘 추가

const ControlPanel = () => {
  const { moveRobot } = useRobot();
  const lastSentTime = useRef(0);

  const handleMove = (event) => {
    // 0.1초 간격 전송 제한 (서버 부하 방지)
    const now = Date.now();
    if (now - lastSentTime.current < 100) return;
    lastSentTime.current = now;

    // 조이스틱 데이터 변환
    const linear = event.y || 0;
    const angular = -event.x || 0; // 좌우 반전

    moveRobot(linear, angular);
  };

  const handleStop = () => {
    moveRobot(0, 0);
    // console.log("🛑 Stop command sent");
  };

  return (
    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col items-center w-full h-full">
      {/* 헤더 */}
      <div className="w-full flex items-center gap-2 mb-6">
        <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
          <Gamepad2 size={20} />
        </div>
        <h3 className="font-bold text-gray-800">수동 제어</h3>
      </div>

      {/* 조이스틱 영역 */}
      <div className="flex-1 flex flex-col justify-center items-center gap-4">
        <div className="p-4 bg-gray-50 rounded-full border border-gray-100 shadow-inner">
          <Joystick 
            size={120} 
            sticky={false} 
            baseColor="#e5e7eb" // 회색 (Tailwind gray-200)
            stickColor="#6366f1" // 인디고 (Tailwind indigo-500)
            move={handleMove} 
            stop={handleStop}
            throttle={100} 
          />
        </div>
        <p className="text-xs text-gray-400 font-medium">
          조이스틱을 드래그하여 이동
        </p>
      </div>
    </div>
  );
};

export default ControlPanel;