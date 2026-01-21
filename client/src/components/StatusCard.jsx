import { useEffect, useState } from 'react';
import api from '../../api/axios'; // 🚨 수정 1: 그냥 axios 말고 우리가 만든 api 인스턴스 사용!
import { Battery, Thermometer, Zap, Activity } from 'lucide-react';

const StatusCard = () => {
  const [status, setStatus] = useState({
    batteryLevel: 0,
    temperature: 0.0,
    charging: false
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        // 🚨 수정 1의 결과: 이제 요청 보낼 때 토큰이 자동으로 같이 갑니다.
        const res = await api.get('/robot/latest'); 
        if (res.data) {
            setStatus(res.data);
        }
      } catch (err) {
        console.error("로봇 상태 조회 실패:", err);
      }
    };

    fetchData(); 
    const interval = setInterval(fetchData, 1000); 

    return () => clearInterval(interval); 
  }, []);

  return (
    // 🎨 수정 2: Tailwind CSS로 디자인 통일 (흰색 배경)
    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm h-full">
      <div className="flex items-center gap-2 mb-6">
        <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
          <Activity size={20} />
        </div>
        <h3 className="font-bold text-gray-800">로봇 상태</h3>
      </div>
      
      <div className="grid grid-cols-3 gap-4 text-center divide-x divide-gray-100">
        
        {/* 1. 배터리 */}
        <div className="flex flex-col items-center gap-2">
          <div className={`p-2 rounded-full ${status.batteryLevel > 20 ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
            <Battery size={24} />
          </div>
          <div>
            <span className="block text-2xl font-bold text-gray-800">{status.batteryLevel}%</span>
            <span className="text-xs text-gray-500">배터리</span>
          </div>
        </div>
        
        {/* 2. 온도 */}
        <div className="flex flex-col items-center gap-2">
          <div className="p-2 rounded-full bg-orange-50 text-orange-500">
            <Thermometer size={24} />
          </div>
          <div>
            <span className="block text-2xl font-bold text-gray-800">{status.temperature.toFixed(1)}°C</span>
            <span className="text-xs text-gray-500">내부 온도</span>
          </div>
        </div>

        {/* 3. 충전 상태 */}
        <div className="flex flex-col items-center gap-2">
          <div className={`p-2 rounded-full ${status.charging ? 'bg-yellow-50 text-yellow-600' : 'bg-gray-100 text-gray-400'}`}>
            <Zap size={24} fill={status.charging ? "currentColor" : "none"} />
          </div>
          <div>
            <span className="block text-sm font-bold text-gray-800 mt-1">
              {status.charging ? "충전 중" : "사용 중"}
            </span>
            <span className="text-xs text-gray-500">전원 상태</span>
          </div>
        </div>

      </div>
    </div>
  );
};

export default StatusCard;