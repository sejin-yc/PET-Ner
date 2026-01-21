import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom'; // 회원탈퇴 후 이동용
import api from '../api/axios'; // 회원탈퇴용 API 직접 호출
import { toast } from 'sonner';
import { User, Lock, Camera, LogOut, Shield, AlertTriangle, CheckCircle } from 'lucide-react';

const SettingsPage = () => {
  const { user, logout, updateProfile, changePassword } = useAuth();
  const navigate = useNavigate();

  // ✅ 상태 1: 비밀번호 검증 여부 (false면 잠김)
  const [isVerified, setIsVerified] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');

  // 상태 2: 설정 폼 데이터
  const [name, setName] = useState(user?.name || '');
  const [passwords, setPasswords] = useState({ current: '', new: '', confirm: '' });
  const [profileImage, setProfileImage] = useState(null); // (추후 구현용 미리보기)

  // 🔐 1. 비밀번호 확인 핸들러 (Gate)
  const handleVerifyPassword = async (e) => {
    e.preventDefault();
    try {
      // 백엔드에 비밀번호 확인 요청
      await api.post('/users/verify-password', { 
        userId: user.id, 
        password: passwordInput 
      });
      
      setIsVerified(true); // 성공 시 잠금 해제
      toast.success("본인 확인이 완료되었습니다.");
    } catch (error) {
      toast.error("비밀번호가 일치하지 않습니다.");
    }
  };

  // 🖼️ 2. 프로필 사진 업로드 (UI 시뮬레이션)
  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      // 실제 업로드는 나중에 구현하더라도 미리보기는 가능하게
      const reader = new FileReader();
      reader.onloadend = () => {
        setProfileImage(reader.result); // Base64 미리보기 설정
      };
      reader.readAsDataURL(file);
    }
  };

  // 💾 3. 프로필 저장 (이름 변경)
  const handleSaveProfile = async () => {
    if (!name.trim()) return toast.error("이름을 입력해주세요.");
    await updateProfile(name);
    // 사진 업로드 로직은 백엔드 파일 서버 구현 후 추가 예정
  };

  // 🔑 4. 비밀번호 변경
  const handleChangePassword = async () => {
    if (passwords.new !== passwords.confirm) return toast.error("새 비밀번호가 일치하지 않습니다.");
    if (passwords.new.length < 6) return toast.error("비밀번호는 6자 이상이어야 합니다.");
    
    const success = await changePassword(passwords.current, passwords.new);
    if(success) setPasswords({ current: '', new: '', confirm: '' });
  };

  // 🚨 5. 회원 탈퇴
  const handleDeleteAccount = async () => {
    if (!confirm("정말로 탈퇴하시겠습니까? 이 작업은 되돌릴 수 없습니다.")) return;

    try {
      await api.delete(`/users/${user.id}`); // 백엔드 탈퇴 API 호출
      toast.success("회원 탈퇴가 완료되었습니다.");
      logout(); // 로그아웃 처리
      navigate('/login'); // 로그인 페이지로 이동
    } catch (error) {
      toast.error("탈퇴 처리에 실패했습니다.");
    }
  };

  // 🔒 화면 1: 비밀번호 잠금 화면
  if (!isVerified) {
    return (
      <div className="max-w-md mx-auto mt-20 p-8 bg-white rounded-xl shadow-lg border border-gray-200 text-center">
        <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Lock size={32} className="text-gray-500" />
        </div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">본인 확인</h2>
        <p className="text-sm text-gray-500 mb-6">개인정보 보호를 위해 비밀번호를 입력해주세요.</p>
        
        <form onSubmit={handleVerifyPassword} className="space-y-4">
          <input 
            type="password" 
            value={passwordInput}
            onChange={(e) => setPasswordInput(e.target.value)}
            placeholder="현재 비밀번호"
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
            autoFocus
          />
          <button type="submit" className="w-full bg-indigo-600 text-white py-3 rounded-lg font-bold hover:bg-indigo-700 transition-colors">
            확인
          </button>
        </form>
      </div>
    );
  }

  // 🔓 화면 2: 설정 대시보드 (검증 통과 후)
  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-20">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800">계정 설정</h1>
        <span className="text-sm text-green-600 bg-green-50 px-3 py-1 rounded-full flex items-center gap-1">
          <CheckCircle size={14}/> 본인 인증됨
        </span>
      </div>

      {/* 1. 프로필 설정 */}
      <section className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-lg font-semibold flex items-center gap-2 mb-6 border-b pb-4">
          <User size={20} className="text-indigo-600"/> 프로필 설정
        </h2>
        
        <div className="flex flex-col md:flex-row gap-8 items-center md:items-start">
          {/* 사진 업로드 */}
          <div className="flex flex-col items-center gap-3">
            <div className="w-32 h-32 rounded-full bg-gray-100 border-4 border-white shadow-md overflow-hidden relative group">
              {profileImage ? (
                <img src={profileImage} alt="Profile" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-300 bg-gray-50">
                  <User size={48} />
                </div>
              )}
              <label className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer text-white">
                <Camera size={24} />
                <input type="file" className="hidden" accept="image/*" onChange={handleImageChange} />
              </label>
            </div>
            <span className="text-xs text-gray-500">사진 변경 클릭</span>
          </div>

          {/* 정보 입력 */}
          <div className="flex-1 w-full space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">이메일</label>
              <input type="email" value={user?.email} disabled className="w-full mt-1 p-2 bg-gray-100 border rounded text-gray-500 cursor-not-allowed"/>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">이름 (닉네임)</label>
              <div className="flex gap-2 mt-1">
                <input 
                  type="text" 
                  value={name} 
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500 outline-none"
                />
                <button onClick={handleSaveProfile} className="bg-indigo-600 text-white px-4 rounded hover:bg-indigo-700 whitespace-nowrap">
                  저장
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. 비밀번호 변경 */}
      <section className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-lg font-semibold flex items-center gap-2 mb-6 border-b pb-4">
          <Lock size={20} className="text-gray-700"/> 비밀번호 변경
        </h2>
        <div className="grid gap-4 max-w-md">
          <input 
            type="password" 
            placeholder="현재 비밀번호" 
            value={passwords.current}
            onChange={(e) => setPasswords({...passwords, current: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded"
          />
          <input 
            type="password" 
            placeholder="새 비밀번호 (6자 이상)" 
            value={passwords.new}
            onChange={(e) => setPasswords({...passwords, new: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded"
          />
          <input 
            type="password" 
            placeholder="새 비밀번호 확인" 
            value={passwords.confirm}
            onChange={(e) => setPasswords({...passwords, confirm: e.target.value})}
            className="w-full p-2 border border-gray-300 rounded"
          />
          <button onClick={handleChangePassword} className="w-full bg-gray-800 text-white py-2 rounded hover:bg-black font-medium">
            비밀번호 변경하기
          </button>
        </div>
      </section>

      {/* 3. 위험 구역 (로그아웃 / 탈퇴) */}
      <section className="bg-red-50 p-6 rounded-xl border border-red-100">
        <h2 className="text-lg font-semibold flex items-center gap-2 mb-4 text-red-700">
          <AlertTriangle size={20}/> 위험 구역
        </h2>
        <div className="flex flex-col md:flex-row gap-4">
          <button onClick={logout} className="flex-1 bg-white border border-red-200 text-red-600 py-3 rounded-lg hover:bg-red-50 flex justify-center items-center gap-2 font-medium">
            <LogOut size={18}/> 로그아웃
          </button>
          <button onClick={handleDeleteAccount} className="flex-1 bg-red-600 text-white py-3 rounded-lg hover:bg-red-700 flex justify-center items-center gap-2 font-medium shadow-sm">
            <Shield size={18}/> 회원 탈퇴
          </button>
        </div>
        <p className="text-xs text-red-400 mt-3 text-center md:text-left">
          * 회원 탈퇴 시 모든 데이터(로그, 영상 등)가 영구적으로 삭제됩니다.
        </p>
      </section>
    </div>
  );
};

export default SettingsPage;