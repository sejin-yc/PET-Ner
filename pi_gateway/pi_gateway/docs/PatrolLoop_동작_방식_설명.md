# PatrolLoop 동작 방식 설명

PatrolLoop가 어떻게 경로를 따라가는지 설명합니다.

---

## 🎯 핵심 답변

**PatrolLoop는 랜덤이 아니라 정해진 패턴을 반복합니다!**

---

## 🔄 동작 방식

### 기본 패턴

```python
segments = [
    PatrolSegment(duration_s=2.0, vx_mps=0.15, wz_rps=0.0),  # 구간 1: 앞으로 2초
    PatrolSegment(duration_s=1.2, vx_mps=0.0, wz_rps=0.7),   # 구간 2: 회전 1.2초
]
```

**동작 순서:**
1. **앞으로 2초** (vx=0.15 m/s, wz=0.0 rad/s)
2. **회전 1.2초** (vx=0.0 m/s, wz=0.7 rad/s)
3. **앞으로 2초** (다시 구간 1로)
4. **회전 1.2초** (다시 구간 2로)
5. **무한 반복** 🔄

### 코드 분석

```python
class PatrolProfile:
    def step(self, dt: float) -> Tuple[float, float]:
        self._seg_elapsed += dt  # 경과 시간 누적
        
        seg = self.cfg.segments[self._seg_idx]  # 현재 구간
        
        # 구간 시간이 지나면 다음 구간으로
        while self._seg_elapsed >= seg.duration_s and seg.duration_s > 0:
            self._seg_elapsed -= seg.duration_s
            self._seg_idx = (self._seg_idx + 1) % len(self.cfg.segments)  # 순환
            seg = self.cfg.segments[self._seg_idx]
        
        return seg.vx_mps, seg.wz_rps  # 현재 구간의 속도 반환
```

**핵심:**
- `_seg_idx = (_seg_idx + 1) % len(self.cfg.segments)` 
- **순환 구조**: 구간을 끝까지 가면 다시 처음으로 돌아감
- **랜덤 없음**: 항상 같은 순서로 반복

---

## 📊 예시

### 기본 패턴 (2개 구간)

```
시간: 0초 ──→ 2초 ──→ 3.2초 ──→ 5.2초 ──→ 6.4초 ──→ ...
      │        │        │         │         │
      ▼        ▼        ▼         ▼         ▼
    앞으로   회전    앞으로    회전    앞으로
    (2초)   (1.2초)  (2초)    (1.2초)  (2초)
```

### 커스텀 패턴 예시

더 복잡한 패턴을 만들 수도 있습니다:

```python
segments = [
    PatrolSegment(duration_s=3.0, vx_mps=0.2, wz_rps=0.0),   # 앞으로 3초
    PatrolSegment(duration_s=0.5, vx_mps=0.0, wz_rps=1.0),   # 빠르게 회전 0.5초
    PatrolSegment(duration_s=2.0, vx_mps=0.1, wz_rps=0.0),   # 천천히 앞으로 2초
    PatrolSegment(duration_s=1.0, vx_mps=0.0, wz_rps=-0.5),  # 반대 방향 회전 1초
]
```

**동작 순서:**
1. 앞으로 3초
2. 빠르게 회전 0.5초
3. 천천히 앞으로 2초
4. 반대 방향 회전 1초
5. 다시 처음으로 (앞으로 3초...)

---

## ⚠️ 특징

### 장점
- ✅ **예측 가능**: 항상 같은 패턴 반복
- ✅ **간단**: 복잡한 경로 계획 불필요
- ✅ **안정적**: 장애물 회피 없이 단순 이동

### 단점
- ❌ **장애물 회피 없음**: 벽이나 장애물을 만나면 멈추지 않음
- ❌ **경로 계획 없음**: 목표 위치로 이동하지 않음
- ❌ **Nav2 없음**: SLAM/경로 계획 기능 없음

---

## 🎯 사용 목적

**PatrolLoop는 Nav2가 없을 때 임시로 사용하는 단순 패턴입니다.**

- **Nav2 전**: 단순 패턴으로 순찰 (현재)
- **Nav2 후**: Nav2가 `cmd_vel_auto`를 발행하면 PatrolLoop는 무시됨

---

## 💡 요약

**PatrolLoop는:**
- ✅ **정해진 패턴을 반복** (랜덤 아님)
- ✅ **순환 구조**: 구간을 끝까지 가면 다시 처음으로
- ✅ **Nav2 전 임시용**: Nav2가 있으면 Nav2 명령 사용

**기본 패턴:**
- 앞으로 2초 → 회전 1.2초 → 앞으로 2초 → 회전 1.2초 → ...

**커스터마이징:**
- `PatrolConfig.segments`를 수정하여 원하는 패턴 설정 가능
