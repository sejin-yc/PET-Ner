# ⚙️ Robot Kinematics & Specs

## 1. Robot Specifications
* **Wheel Type:** Mecanum Wheel (97mm Diameter)
* **Dimensions:**
    * Length (L): 300 mm
    * Width (W): 350 mm
* **Kinematic Parameters:**
    * **Wheelbase ($2 \cdot l_x$):** 230 mm (Front-Rear Axle distance)
    * **Track Width ($2 \cdot l_y$):** 280 mm (Left-Right Wheel distance)

## 2. Mecanum Wheel Kinematics
본 로봇은 4륜 독립 구동 메카넘 휠을 사용하여 전방향(Holonomic) 이동이 가능합니다.

### Inverse Kinematics (속도 → 모터 RPM)
로봇의 목표 속도 $(v_x, v_y, \omega_z)$가 주어졌을 때, 각 바퀴의 각속도는 다음과 같이 계산됩니다.

$$
\begin{bmatrix} \omega_{FL} \\ \omega_{FR} \\ \omega_{RL} \\ \omega_{RR} \end{bmatrix} = \frac{1}{r} \begin{bmatrix} 1 & -1 & -(l_x + l_y) \\ 1 & 1 & (l_x + l_y) \\ 1 & 1 & -(l_x + l_y) \\ 1 & -1 & (l_x + l_y) \end{bmatrix} \begin{bmatrix} v_x \\ v_y \\ \omega_z \end{bmatrix}
$$

* $v_x$: 전진 속도
* $v_y$: 좌/우 평행이동 속도
* $\omega_z$: 회전 각속도
* $l_x = 115mm$, $l_y = 140mm$

## 3. Movement Logic (Current Implementation)
현재 펌웨어(`main.c`)에는 다음과 같은 기본 기동 로직이 구현되어 있습니다.

* **Forward (w):** All Wheels Forward (+)
* **Slide Left (a):** FL(-), FR(+), RL(+), RR(-)
* **Slide Right (d):** FL(+), FR(-), RL(-), RR(+)
* **Rotate Left (q):** FL(-), FR(+), RL(-), RR(+)

