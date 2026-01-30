# ⚡ Power Architecture

본 로봇은 3S LiPo 배터리를 메인 전원으로 사용하며, 각 컴포넌트의 전압 요구 사양에 맞춰 3단 분배 시스템을 구축했습니다.

## 🔋 전원 분배 구조
![Power Distribution](./images/mechanical/control_board_schematic.png)

### 층별 전원 구현 상세
1. **Tier 1: 구동부 (12.6V Raw)**
    - 배터리 전원을 모터 드라이버에 직접 공급하여 최대 토크 확보.
    ![Tier 1 View](./images/mechanical/tier1_chassis_base_view.jpg)

2. **Tier 2: 전원 변환부 (Regulated Logic)**
    - **XL4016:** 12.6V → 5.1V (Raspberry Pi 5 전용)
    - **XL4015:** 12.6V → 5.0V (STM32 및 센서 로직용)
    - **LTC3780:** 로봇팔 구동을 위한 전압 안정화 (12V)
    ![Tier 2 View](./images/mechanical/tier2_chassis_view.jpg)

3. **Tier 3: 메인 전원 (Source)**
    - 배터리 및 BMS가 위치하여 전체 시스템 전력 공급.
    ![Tier 3 View](./images/mechanical/tier3_chassis_view.jpg)

## 🛡️ 안전 대책 및 검증
- **Common Ground:** 전위차 제거를 위한 통합 GND 망 구축. [GND 보강](./images/hardware/hardware_wiring_back.jpg)
- **Voltage Scaling:** 배터리 전압(12.6V)을 ADC 안전 범위로 감압 (10k:3.3k 분배).
    - 실측 데이터: 6V 입력 시 **1.48V** 출력 확인 (이론값 1.488V와 일치).
    ![Voltage Verification](./images/hardware/voltage_divider_test.jpg)