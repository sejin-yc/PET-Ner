/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : F446RE Syringe Control (Fix: RPi Command Support)
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* Private variables ---------------------------------------------------------*/
I2C_HandleTypeDef hi2c1;

TIM_HandleTypeDef htim1;
TIM_HandleTypeDef htim2;
TIM_HandleTypeDef htim3;
TIM_HandleTypeDef htim4;
TIM_HandleTypeDef htim8;  // 모터 PWM
TIM_HandleTypeDef htim12; // 서보 PWM (CH1: PB14, CH2: PB15)

UART_HandleTypeDef huart4; // RPi
UART_HandleTypeDef huart2; // PC

/* USER CODE BEGIN PV */
// [튜닝 파라미터]
#define PWM_LIMIT 999
#define MAX_TARGET_SPEED 400
#define SPEED_STEP 400

// 서보 1 (기존 360도 - PB15)
#define SERVO_CCW  1000
#define SERVO_STOP 1500
#define SERVO_CW   2000
#define SERVO_RUN_TIME 10000

// 서보 2 (주사기 - PB14)
#define SERVO2_MIN 500  // 0도 기준 펄스
#define SERVO2_MAX 2500 // 180도 기준 펄스

uint8_t rx_data_pc;
uint8_t rx_data_rpi;
volatile uint8_t new_key_received = 0;
char last_key = 's';
char tx_buffer[128];

int16_t user_set_speed = 0;

// [제어 모드]
// 0: 주행 모드 (기본)
// 1: PWM 직접 입력 모드 (p)
uint8_t control_mode = 0;
char input_buffer[10];
uint8_t input_idx = 0;

// [누적 벡터]
int current_vx = 0;
int current_vy = 0;
int current_omega = 0;

uint16_t servo1_pulse = SERVO_STOP; // PB15 (360)
uint16_t servo2_pulse = 1500;       // PB14 (주사기)

// [NEW] 주사기 각도 변수 (초기값 5도)
int servo2_angle = 5;

uint8_t is_servo1_running = 0;
uint32_t servo1_start_time = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM1_Init(void);
static void MX_TIM2_Init(void);
static void MX_TIM3_Init(void);
static void MX_TIM4_Init(void);
static void MX_TIM8_Init(void);
static void MX_TIM12_Init(void);
static void MX_UART4_Init(void);

/* USER CODE BEGIN PFP */
int32_t clamp(int32_t value, int32_t min, int32_t max);
long map(long x, long in_min, long in_max, long out_min, long out_max);
void set_motor_state(int fl, int fr, int rl, int rr);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
int32_t clamp(int32_t value, int32_t min, int32_t max) {
    if (value > max) return max;
    if (value < min) return min;
    return value;
}

// 각도 -> 펄스 변환 함수
long map(long x, long in_min, long in_max, long out_min, long out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

void set_motor_state(int fl, int fr, int rl, int rr)
{
    fl = clamp(fl, -PWM_LIMIT, PWM_LIMIT);
    fr = clamp(fr, -PWM_LIMIT, PWM_LIMIT);
    rl = clamp(rl, -PWM_LIMIT, PWM_LIMIT);
    rr = clamp(rr, -PWM_LIMIT, PWM_LIMIT);

    if (fl > 0) HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_SET);
    else        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_RESET);
    __HAL_TIM_SET_COMPARE(&htim8, TIM_CHANNEL_1, abs(fl));

    if (fr > 0) HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1, GPIO_PIN_SET);
    else        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1, GPIO_PIN_RESET);
    __HAL_TIM_SET_COMPARE(&htim8, TIM_CHANNEL_2, abs(fr));

    if (rl > 0) HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, GPIO_PIN_SET);
    else        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, GPIO_PIN_RESET);
    __HAL_TIM_SET_COMPARE(&htim8, TIM_CHANNEL_3, abs(rl));

    if (rr > 0) HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_SET);
    else        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_RESET);
    __HAL_TIM_SET_COMPARE(&htim8, TIM_CHANNEL_4, abs(rr));
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if(huart->Instance == USART2) { // PC

    // --- [모드 1] PWM 속도 입력 ---
    if (control_mode == 1) {
        HAL_UART_Transmit(&huart2, &rx_data_pc, 1, 10);
        if (rx_data_pc == '\r' || rx_data_pc == '\n') {
            input_buffer[input_idx] = '\0';
            int new_val = atoi(input_buffer);
            if (new_val >= 0 && new_val <= 999) user_set_speed = new_val;
            sprintf(tx_buffer, "\r\n>> Speed Set: %d\r\n", user_set_speed);
            HAL_UART_Transmit(&huart2, (uint8_t*)tx_buffer, strlen(tx_buffer), 100);
            control_mode = 0; // 복귀
        } else if (input_idx < 9 && rx_data_pc >= '0' && rx_data_pc <= '9') {
            input_buffer[input_idx++] = rx_data_pc;
        }
    }
    // --- [모드 0] 일반 주행 + 키보드 제어 ---
    else {
        if (rx_data_pc == 'p' || rx_data_pc == 'P') {
            // PWM 입력 모드로 진입
            current_vx=0; current_vy=0; current_omega=0;
            control_mode=1; input_idx=0;
            char *msg = "\r\n[Input Speed (0-999)]: ";
            HAL_UART_Transmit(&huart2, (uint8_t*)msg, strlen(msg), 100);

        } else {
            // [중요 수정] k 로직을 여기서 제거하고 main 루프로 이동
            // 이제 k가 들어오면 last_key에 저장되어 main()에서 처리됨
            last_key = (char)rx_data_pc;
            new_key_received = 1;
        }
    }
    HAL_UART_Receive_IT(&huart2, &rx_data_pc, 1);
  }

  if(huart->Instance == UART4) { // RPi
      if(control_mode == 0) {
          last_key = (char)rx_data_rpi;
          new_key_received = 1;
      }
      HAL_UART_Receive_IT(&huart4, &rx_data_rpi, 1);
  }
}
/* USER CODE END 0 */

int main(void)
{
  HAL_Init();
  SystemClock_Config();

  MX_GPIO_Init();
  MX_TIM8_Init();
  MX_USART2_UART_Init();
  MX_I2C1_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  MX_TIM4_Init();
  MX_TIM12_Init();
  MX_UART4_Init();

  HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_1);
  HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_2);
  HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_3);
  HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_4);
  __HAL_TIM_MOE_ENABLE(&htim8);

  HAL_TIM_PWM_Start(&htim12, TIM_CHANNEL_1);
  HAL_TIM_PWM_Start(&htim12, TIM_CHANNEL_2);

  HAL_UART_Receive_IT(&huart4, &rx_data_rpi, 1);
  HAL_UART_Receive_IT(&huart2, &rx_data_pc, 1);

  // [초기 상태 설정] 시작하자마자 주사기를 5도 위치로!
  servo2_angle = 5;
  servo2_pulse = (uint16_t)map(servo2_angle, 0, 180, SERVO2_MIN, SERVO2_MAX);

  printf("\r\n=== F446RE Syringe Control (5~145 deg) ===\r\n");

  while (1)
  {
      // [A] 키 입력 처리 (주행 + 기능)
      if (new_key_received && control_mode == 0)
      {
          new_key_received = 0;
          switch(last_key)
          {
              case 'w': current_vx -= SPEED_STEP; break;
              case 'x': current_vx += SPEED_STEP; break;
              case 'a': current_vy -= SPEED_STEP; break;
              case 'd': current_vy += SPEED_STEP; break;
              case 'q': current_omega -= SPEED_STEP; break;
              case 'e': current_omega += SPEED_STEP; break;

              case 's':
                  current_vx=0; current_vy=0; current_omega=0;
                  //servo1_pulse=SERVO_STOP; is_servo1_running=0;
                  break;

              // 서보 1 (PB15 - 360도)
              case 'i': if(!is_servo1_running) { servo1_pulse=SERVO_CW; servo1_start_time=HAL_GetTick(); is_servo1_running=1; } break;
              case 'u': servo1_pulse=SERVO_CCW; is_servo1_running=0; break;
              case 'o': servo1_pulse=SERVO_CW;  is_servo1_running=0; break;

              // [NEW] 주사기 제어 로직을 여기로 통합 (PC, RPi 모두 작동)
              case 'k':
              case 'K':
                  servo2_angle += 35;
                  if (servo2_angle > 145) servo2_angle = 5;

                  servo2_pulse = (uint16_t)map(servo2_angle, 0, 180, SERVO2_MIN, SERVO2_MAX);

                  // PC 터미널로 상태 전송 (누가 눌렀든 PC에서 확인 가능)
                  sprintf(tx_buffer, "\r\n[Syringe] Angle: %d (Pulse: %d)\r\n", servo2_angle, servo2_pulse);
                  HAL_UART_Transmit(&huart2, (uint8_t*)tx_buffer, strlen(tx_buffer), 10);
                  break;
          }
          current_vx = clamp(current_vx, -MAX_TARGET_SPEED, MAX_TARGET_SPEED);
          current_vy = clamp(current_vy, -MAX_TARGET_SPEED, MAX_TARGET_SPEED);
          current_omega = clamp(current_omega, -MAX_TARGET_SPEED, MAX_TARGET_SPEED);
      }

      // [B] 서보 1 자동 정지
      if (is_servo1_running && (HAL_GetTick() - servo1_start_time >= SERVO_RUN_TIME)) {
          servo1_pulse = SERVO_STOP;
          is_servo1_running = 0;
      }

      // [C] 메카넘 계산
      int cal_fl = current_vx - current_vy - current_omega;
      int cal_fr = current_vx + current_vy + current_omega;
      int cal_rl = current_vx + current_vy - current_omega;
      int cal_rr = current_vx - current_vy + current_omega;

      // [D] 출력 업데이트
      set_motor_state(cal_fl, cal_fr, cal_rl, cal_rr);

      // 서보 1 (PB15 - 360도)
      __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_2, servo1_pulse);

      // 서보 2 (PB14 - 주사기 각도)
      __HAL_TIM_SET_COMPARE(&htim12, TIM_CHANNEL_1, servo2_pulse);

      // [E] 모니터링
      static uint32_t last_print = 0;
      if (HAL_GetTick() - last_print > 200) {
          if(control_mode == 0) {
              sprintf(tx_buffer, "KEY:%c | FL:%d FR:%d | Syringe:%d deg\r\n", last_key, cal_fl, cal_fr, servo2_angle);
              HAL_UART_Transmit(&huart2, (uint8_t*)tx_buffer, strlen(tx_buffer), 10);
          }
          last_print = HAL_GetTick();
      }
      HAL_Delay(10);
  }
}

// TIM12 초기화
static void MX_TIM12_Init(void)
{
  __HAL_RCC_TIM12_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  GPIO_InitTypeDef GPIO_InitStruct = {0};
  GPIO_InitStruct.Pin = GPIO_PIN_14 | GPIO_PIN_15;
  GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  GPIO_InitStruct.Alternate = GPIO_AF9_TIM12;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  TIM_OC_InitTypeDef sConfigOC = {0};
  htim12.Instance = TIM12;
  htim12.Init.Prescaler = 89;
  htim12.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim12.Init.Period = 19999;
  htim12.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim12.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;

  if (HAL_TIM_PWM_Init(&htim12) != HAL_OK) Error_Handler();

  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 1500;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;

  if (HAL_TIM_PWM_ConfigChannel(&htim12, &sConfigOC, TIM_CHANNEL_1) != HAL_OK) Error_Handler();
  if (HAL_TIM_PWM_ConfigChannel(&htim12, &sConfigOC, TIM_CHANNEL_2) != HAL_OK) Error_Handler();
}

// (나머지 초기화 함수 생략 - 동일)
static void MX_TIM8_Init(void) {
  __HAL_RCC_TIM8_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  GPIO_InitStruct.Pin = GPIO_PIN_6|GPIO_PIN_7|GPIO_PIN_8|GPIO_PIN_9;
  GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  GPIO_InitStruct.Alternate = GPIO_AF3_TIM8;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};
  TIM_BreakDeadTimeConfigTypeDef sBreakDeadTimeConfig = {0};
  htim8.Instance = TIM8;
  htim8.Init.Prescaler = 179;
  htim8.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim8.Init.Period = 999;
  htim8.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim8.Init.RepetitionCounter = 0;
  htim8.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
  HAL_TIM_PWM_Init(&htim8);
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  HAL_TIMEx_MasterConfigSynchronization(&htim8, &sMasterConfig);
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCNPolarity = TIM_OCNPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  sConfigOC.OCIdleState = TIM_OCIDLESTATE_RESET;
  sConfigOC.OCNIdleState = TIM_OCNIDLESTATE_RESET;
  HAL_TIM_PWM_ConfigChannel(&htim8, &sConfigOC, TIM_CHANNEL_1);
  HAL_TIM_PWM_ConfigChannel(&htim8, &sConfigOC, TIM_CHANNEL_2);
  HAL_TIM_PWM_ConfigChannel(&htim8, &sConfigOC, TIM_CHANNEL_3);
  HAL_TIM_PWM_ConfigChannel(&htim8, &sConfigOC, TIM_CHANNEL_4);
  sBreakDeadTimeConfig.OffStateRunMode = TIM_OSSR_DISABLE;
  sBreakDeadTimeConfig.OffStateIDLEMode = TIM_OSSI_DISABLE;
  sBreakDeadTimeConfig.LockLevel = TIM_LOCKLEVEL_OFF;
  sBreakDeadTimeConfig.DeadTime = 0;
  sBreakDeadTimeConfig.BreakState = TIM_BREAK_DISABLE;
  sBreakDeadTimeConfig.BreakPolarity = TIM_BREAKPOLARITY_HIGH;
  sBreakDeadTimeConfig.AutomaticOutput = TIM_AUTOMATICOUTPUT_DISABLE;
  HAL_TIMEx_ConfigBreakDeadTime(&htim8, &sBreakDeadTimeConfig);
  HAL_TIM_MspPostInit(&htim8);
}
void SystemClock_Config(void) {
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 180;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 2;
  RCC_OscInitStruct.PLL.PLLR = 2;
  HAL_RCC_OscConfig(&RCC_OscInitStruct);
  HAL_PWREx_EnableOverDrive();
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;
  HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5);
}
static void MX_GPIO_Init(void) { GPIO_InitTypeDef GPIO_InitStruct = {0}; __HAL_RCC_GPIOC_CLK_ENABLE(); __HAL_RCC_GPIOH_CLK_ENABLE(); __HAL_RCC_GPIOA_CLK_ENABLE(); __HAL_RCC_GPIOB_CLK_ENABLE(); HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2|GPIO_PIN_10, GPIO_PIN_RESET); GPIO_InitStruct.Pin = GPIO_PIN_13; GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING; GPIO_InitStruct.Pull = GPIO_NOPULL; HAL_GPIO_Init(GPIOC, &GPIO_InitStruct); GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2|GPIO_PIN_10; GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP; GPIO_InitStruct.Pull = GPIO_NOPULL; GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW; HAL_GPIO_Init(GPIOB, &GPIO_InitStruct); }
static void MX_I2C1_Init(void) { hi2c1.Instance = I2C1; hi2c1.Init.ClockSpeed = 100000; hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2; hi2c1.Init.OwnAddress1 = 0; hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT; hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE; hi2c1.Init.OwnAddress2 = 0; hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE; hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE; HAL_I2C_Init(&hi2c1); }
static void MX_TIM1_Init(void) { TIM_Encoder_InitTypeDef sConfig = {0}; TIM_MasterConfigTypeDef sMasterConfig = {0}; htim1.Instance = TIM1; htim1.Init.Prescaler = 0; htim1.Init.CounterMode = TIM_COUNTERMODE_UP; htim1.Init.Period = 65535; htim1.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1; htim1.Init.RepetitionCounter = 0; htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE; sConfig.EncoderMode = TIM_ENCODERMODE_TI12; sConfig.IC1Polarity = TIM_ICPOLARITY_RISING; sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC1Prescaler = TIM_ICPSC_DIV1; sConfig.IC1Filter = 10; sConfig.IC2Polarity = TIM_ICPOLARITY_RISING; sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC2Prescaler = TIM_ICPSC_DIV1; sConfig.IC2Filter = 10; HAL_TIM_Encoder_Init(&htim1, &sConfig); sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET; sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE; HAL_TIMEx_MasterConfigSynchronization(&htim1, &sMasterConfig); }
static void MX_TIM2_Init(void) { TIM_Encoder_InitTypeDef sConfig = {0}; TIM_MasterConfigTypeDef sMasterConfig = {0}; htim2.Instance = TIM2; htim2.Init.Prescaler = 0; htim2.Init.CounterMode = TIM_COUNTERMODE_UP; htim2.Init.Period = 65535; htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1; htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE; sConfig.EncoderMode = TIM_ENCODERMODE_TI12; sConfig.IC1Polarity = TIM_ICPOLARITY_RISING; sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC1Prescaler = TIM_ICPSC_DIV1; sConfig.IC1Filter = 10; sConfig.IC2Polarity = TIM_ICPOLARITY_RISING; sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC2Prescaler = TIM_ICPSC_DIV1; sConfig.IC2Filter = 10; HAL_TIM_Encoder_Init(&htim2, &sConfig); sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET; sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE; HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig); }
static void MX_TIM3_Init(void) { TIM_Encoder_InitTypeDef sConfig = {0}; TIM_MasterConfigTypeDef sMasterConfig = {0}; htim3.Instance = TIM3; htim3.Init.Prescaler = 0; htim3.Init.CounterMode = TIM_COUNTERMODE_UP; htim3.Init.Period = 65535; htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1; htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE; sConfig.EncoderMode = TIM_ENCODERMODE_TI12; sConfig.IC1Polarity = TIM_ICPOLARITY_RISING; sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC1Prescaler = TIM_ICPSC_DIV1; sConfig.IC1Filter = 10; sConfig.IC2Polarity = TIM_ICPOLARITY_RISING; sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC2Prescaler = TIM_ICPSC_DIV1; sConfig.IC2Filter = 10; HAL_TIM_Encoder_Init(&htim3, &sConfig); sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET; sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE; HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig); }
static void MX_TIM4_Init(void) { TIM_Encoder_InitTypeDef sConfig = {0}; TIM_MasterConfigTypeDef sMasterConfig = {0}; htim4.Instance = TIM4; htim4.Init.Prescaler = 0; htim4.Init.CounterMode = TIM_COUNTERMODE_UP; htim4.Init.Period = 65535; htim4.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1; htim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE; sConfig.EncoderMode = TIM_ENCODERMODE_TI12; sConfig.IC1Polarity = TIM_ICPOLARITY_RISING; sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC1Prescaler = TIM_ICPSC_DIV1; sConfig.IC1Filter = 10; sConfig.IC2Polarity = TIM_ICPOLARITY_RISING; sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI; sConfig.IC2Prescaler = TIM_ICPSC_DIV1; sConfig.IC2Filter = 10; HAL_TIM_Encoder_Init(&htim4, &sConfig); sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET; sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE; HAL_TIMEx_MasterConfigSynchronization(&htim4, &sMasterConfig); }
static void MX_UART4_Init(void) { huart4.Instance = UART4; huart4.Init.BaudRate = 115200; huart4.Init.WordLength = UART_WORDLENGTH_8B; huart4.Init.StopBits = UART_STOPBITS_1; huart4.Init.Parity = UART_PARITY_NONE; huart4.Init.Mode = UART_MODE_TX_RX; huart4.Init.HwFlowCtl = UART_HWCONTROL_NONE; huart4.Init.OverSampling = UART_OVERSAMPLING_16; HAL_UART_Init(&huart4); }
static void MX_USART2_UART_Init(void) { huart2.Instance = USART2; huart2.Init.BaudRate = 115200; huart2.Init.WordLength = UART_WORDLENGTH_8B; huart2.Init.StopBits = UART_STOPBITS_1; huart2.Init.Parity = UART_PARITY_NONE; huart2.Init.Mode = UART_MODE_TX_RX; huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE; huart2.Init.OverSampling = UART_OVERSAMPLING_16; HAL_UART_Init(&huart2); }
void Error_Handler(void) { __disable_irq(); while (1) {} }
