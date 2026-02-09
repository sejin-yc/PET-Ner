import React, { useState } from 'react';
import { useCats } from '@/contexts/PetContext';
import { Plus, Trash2, X, Cat as CatIcon, FileText } from 'lucide-react';

const CatsPage = () => {
  const { cats, addCat, deleteCat } = useCats();
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // 새 고양이 입력 폼 상태
  const [formData, setFormData] = useState({
    name: '', breed: '', age: '', weight: '', notes: ''
  });

  // 고양이 등록 함수
  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Context의 addCat 함수 호출 (DB로 전송)
    // 주의: 서버는 숫자형(int, double)을 기대하므로 형변환 필수
    addCat({
      name: formData.name,
      breed: formData.breed,
      age: Number(formData.age),
      weight: Number(formData.weight),
      notes: formData.notes
    });
    
    // 모달 닫기 및 초기화
    setIsModalOpen(false);
    setFormData({ name: '', breed: '', age: '', weight: '', notes: '' });
  };

  return (
    <div className="space-y-6">
      {/* 상단 헤더 */}
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-gray-900"> 우리집 고양이</h2>
          <p className="text-sm text-gray-500">우리집 반려동물을 등록하고 관리하세요.</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="bg-gray-900 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 hover:bg-black transition-colors"
        >
          <Plus size={16} /> 우리집 고양이 등록
        </button>
      </div>

      {/* 고양이 리스트 (카드 형태) */}
      <div className="space-y-4">
        {!cats || cats.length === 0 ? (
          <div className="text-center py-20 text-gray-400 bg-white rounded-lg border border-dashed">
            등록된 반려동물이 없습니다. 우측 상단 버튼을 눌러 등록해주세요.
          </div>
        ) : (
          cats?.map(cat => (
            <div key={cat.id} className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="bg-indigo-50 p-3 rounded-full text-indigo-600">
                    <CatIcon size={24} />
                  </div>
                  <div>
                    <h3 className="font-bold text-lg flex items-center gap-2">
                      {cat.name}
                      <span className={`text-xs px-2 py-0.5 rounded ${cat.healthStatus === 'normal' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                        {cat.healthStatus === 'normal' ? '정상' : '주의'}
                      </span>
                    </h3>
                    <span className="text-xs text-gray-500">
                      마지막 감지: {cat.lastDetected ? new Date(cat.lastDetected).toLocaleString() : '기록 없음'}
                    </span>
                  </div>
                </div>
                <button 
                  onClick={() => deleteCat(cat.id)} 
                  className="text-gray-400 hover:text-red-500 p-2 transition-colors"
                >
                  <Trash2 size={18} />
                </button>
              </div>

              {/* 상세 정보 그리드 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm border-t border-b border-gray-100 py-4 my-4">
                <div className="flex items-center gap-2 text-gray-600">
                  <span className="w-20 font-medium text-gray-400">품종</span>
                  {cat.breed || '정보 없음'}
                </div>
                <div className="flex items-center gap-2 text-gray-600">
                  <span className="w-20 font-medium text-gray-400">나이</span>
                  {cat.age}살
                </div>
                <div className="flex items-center gap-2 text-gray-600">
                  <span className="w-20 font-medium text-gray-400">체중</span>
                  {cat.weight}kg
                </div>
                <div className="flex items-center gap-2 text-gray-600">
                  <span className="w-20 font-medium text-gray-400">상태</span>
                  {cat.behaviorStatus || '대기 중'}
                </div>
              </div>

              <div className="text-sm text-gray-600 flex gap-2">
                <FileText size={16} className="text-gray-400 shrink-0" />
                <p>{cat.notes || '메모가 없습니다.'}</p>
              </div>
            </div>
          ))
        )}
      </div>

      {/* === 모달: 새 고양이 등록 === */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="flex justify-between items-center p-4 border-b">
              <h3 className="font-bold text-lg">새 고양이 등록</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-gray-500 hover:text-gray-900">
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">이름</label>
                <input 
                  required
                  value={formData.name}
                  onChange={e => setFormData({...formData, name: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-black focus:border-transparent outline-none"
                  placeholder="고양이 이름"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">품종</label>
                <input 
                  value={formData.breed}
                  onChange={e => setFormData({...formData, breed: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-black outline-none"
                  placeholder="예: 코리안 숏헤어"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-sm font-medium">나이 (년)</label>
                  <input 
                    type="number"
                    value={formData.age}
                    onChange={e => setFormData({...formData, age: e.target.value})}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-black outline-none"
                    placeholder="0"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">체중 (kg)</label>
                  <input 
                    type="number" step="0.1"
                    value={formData.weight}
                    onChange={e => setFormData({...formData, weight: e.target.value})}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-black outline-none"
                    placeholder="0.0"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">메모</label>
                <textarea 
                  value={formData.notes}
                  onChange={e => setFormData({...formData, notes: e.target.value})}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-black outline-none min-h-[80px]"
                  placeholder="성격, 특이사항 등..."
                />
              </div>

              <div className="pt-4 flex gap-3">
                <button 
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 py-2.5 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50"
                >
                  취소
                </button>
                <button 
                  type="submit"
                  className="flex-1 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-black"
                >
                  등록
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CatsPage;