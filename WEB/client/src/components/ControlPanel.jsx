import React, { useEffect, useCallback } from 'react';
import { useRobot } from '../contexts/RobotContext';
import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Square, Gamepad2 } from 'lucide-react';

const ControlPanel = () => {
  const { moveRobot } = useRobot();

  const handleCommand = useCallback((key) => {
    const LINEAR_SPEED = 0.5;
    const ANGULAR_SPEED = 1.0;

    switch (key) {
      case 'W':
        moveRobot(LINEAR_SPEED, 0.0);
        break;
      case 'X':
        moveRobot(-LINEAR_SPEED, 0.0);
        break;
      case 'A':
        moveRobot(0.0, ANGULAR_SPEED);
        break;
      case 'D':
        moveRobot(0.0, -ANGULAR_SPEED);
        break;
      case 'S':
        moveRobot(0.0, 0.0);
        break;
      default:
        break;
    }
  }, [moveRobot]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      const key = e.key.toUpperCase();
      if (['W', 'A', 'S', 'D', 'X'].includes(key)) {
        handleCommand(key);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleCommand]);

  const ControlBtn = ({ label, icon: Icon, onClick, colorClass = "text-gray-700", bgClass = "bg-white" }) => (
    <button
      onClick={onClick}
      className={`flex flex-col items-center justify-center w-16 h-16 rounded-2xl shadow-md border border-gray-100
        ${bgClass} hover:bg-gray-50 active:scale-95 active:shadow-inner transition-all duration-200`}
    >
      <Icon size={28} className={`mb-1 ${colorClass}`} strokeWidth={2.5} />
      <span className='text-xs font-bold text-gray-400'>{label}</span>
    </button>
  );

  return (
    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col items-center w-full h-full">
      {/* 헤더 */}
      <div className="w-full flex items-center gap-2 mb-6">
        <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
          <Gamepad2 size={20} />
        </div>
        <h3 className="font-bold text-gray-800">조이스틱</h3>
      </div>

      {/* 조이스틱 영역 */}
      <div className="flex-1 flex flex-col justify-center items-center">
        <div className="grid grid-cols-3 gap-3">
          <div />
          <ControlBtn label="전진" icon={ArrowUp} onClick={() => handleCommand('W')} />
          <div />

          <ControlBtn label="좌회전" icon={ArrowLeft} onClick={() => handleCommand('A')} />
          <ControlBtn
            label="정지"
            icon={Square}
            onClick={() => handleCommand('S')}
            colorClass='text-red-500 fill-current'
            bgClass='bg-red-50/50 border-red-100'
          />
          <ControlBtn label="우회전" icon={ArrowRight} onClick={() => handleCommand('D')} />
          <div />

          <ControlBtn label="후진" icon={ArrowDown} onClick={() => handleCommand('X')} />
          <div />
        </div>

        <p className="mt-6 text-xs text-gray-400 font-medium text-center">
          키보드 <span className='font-bold text-indigo-500'>WASD</span> 및 <span className='font-bold text-indigo-500'>X</span> 키 사용 가능
        </p>
      </div>
    </div>
  );
};

export default ControlPanel;