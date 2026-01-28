import React from 'react';
import { useRobot } from '@/contexts/RobotContext';
import { ClipboardList, Trash2, MapPin, Clock, Search, Calendar } from 'lucide-react';
import LogCharts from '@/components/charts/LogCharts'; // ✅ 차트 컴포넌트 추가

const LogsPage = () => {
  const { logs, deleteLog, addTestLog } = useRobot();

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-20">
      
      {/* 1. 헤더 */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">순찰 로그 (Patrol Logs)</h1>
          <p className="text-sm text-gray-500 mt-1">로봇이 수행한 자율 순찰 기록과 특이사항 리포트입니다.</p>
        </div>
        <button 
          onClick={addTestLog} 
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm"
        >
          + 테스트 로그 생성
        </button>
      </div>

      {/* ✅ 2. 차트 영역 (여기에 추가됨!) */}
      <LogCharts />

      {/* 3. 검색 및 필터 (UI만 존재) */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex gap-3">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
          <input type="text" placeholder="로그 검색..." className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm outline-none focus:border-indigo-500"/>
        </div>
        <select className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm outline-none focus:border-indigo-500 text-gray-600">
          <option>전체 보기</option>
          <option>이상 감지</option>
          <option>일반 순찰</option>
        </select>
      </div>

      {/* 4. 로그 리스트 */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {logs.length === 0 ? (
          <div className="p-12 text-center text-gray-400 flex flex-col items-center">
            <ClipboardList size={48} className="mb-3 opacity-20" />
            <p>아직 생성된 로그가 없습니다.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {logs.map((log) => (
              <div key={log.id} className="p-5 hover:bg-gray-50 transition-colors flex flex-col md:flex-row md:items-center gap-4 group">
                {/* 아이콘 상태 */}
                <div className={`w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 
                  ${log.detectionCount > 0 ? 'bg-red-50 text-red-500' : 'bg-green-50 text-green-600'}`}>
                  <ClipboardList size={24} />
                </div>

                {/* 내용 */}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-gray-800">
                      {log.mode === 'auto' ? '자동 순찰' : '수동 제어'} 리포트 #{log.id}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                      log.status === 'completed' ? 'bg-blue-50 text-blue-600 border-blue-100' : 'bg-yellow-50 text-yellow-600 border-yellow-100'
                    }`}>
                      {log.status === 'completed' ? '완료됨' : '진행중'}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Calendar size={12}/>
                      {log.createdAt ? new Date(log.createdAt).toLocaleString() : '날짜 없음'}
                    </span>
                    <span className="hidden md:inline text-gray-300">|</span>
                    
                    <span className="flex items-center gap-1"><Clock size={12}/> {log.duration || '0분'}</span>
                    <span className="flex items-center gap-1"><MapPin size={12}/> {log.distance || 0}m 이동</span>
                    {log.detectionCount > 0 && <span className="text-red-500 font-bold">⚠️ 감지 {log.detectionCount}건</span>}
                  </div>
                  <p className="text-sm text-gray-600 mt-2">{log.details}</p>
                </div>

                {/* 삭제 버튼 */}
                <button 
                  onClick={() => deleteLog(log.id)}
                  className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-all opacity-0 group-hover:opacity-100"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default LogsPage;