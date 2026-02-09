/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

void HAL_TIM_MspPostInit(TIM_HandleTypeDef *htim);

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define IMU_INT_Pin GPIO_PIN_13
#define IMU_INT_GPIO_Port GPIOC
#define IMU_RST_Pin GPIO_PIN_14
#define IMU_RST_GPIO_Port GPIOC
#define FL_ENC1_Pin GPIO_PIN_0
#define FL_ENC1_GPIO_Port GPIOA
#define FL_ENC2_Pin GPIO_PIN_1
#define FL_ENC2_GPIO_Port GPIOA
#define RL_ENC1_Pin GPIO_PIN_6
#define RL_ENC1_GPIO_Port GPIOA
#define RL_ENC2_Pin GPIO_PIN_7
#define RL_ENC2_GPIO_Port GPIOA
#define FL_DIR_Pin GPIO_PIN_0
#define FL_DIR_GPIO_Port GPIOB
#define FR_DIR_Pin GPIO_PIN_1
#define FR_DIR_GPIO_Port GPIOB
#define RL_DIR_Pin GPIO_PIN_2
#define RL_DIR_GPIO_Port GPIOB
#define RR_DIR_Pin GPIO_PIN_10
#define RR_DIR_GPIO_Port GPIOB
#define SERVO_180_Pin GPIO_PIN_14
#define SERVO_180_GPIO_Port GPIOB
#define SERVO_360_Pin GPIO_PIN_15
#define SERVO_360_GPIO_Port GPIOB
#define FL_PWM_Pin GPIO_PIN_6
#define FL_PWM_GPIO_Port GPIOC
#define FR_PWM_Pin GPIO_PIN_7
#define FR_PWM_GPIO_Port GPIOC
#define RL_PWM_Pin GPIO_PIN_8
#define RL_PWM_GPIO_Port GPIOC
#define RR_PWM_Pin GPIO_PIN_9
#define RR_PWM_GPIO_Port GPIOC
#define RR_ENC1_Pin GPIO_PIN_8
#define RR_ENC1_GPIO_Port GPIOA
#define RR_ENC2_Pin GPIO_PIN_9
#define RR_ENC2_GPIO_Port GPIOA
#define FR_ENC2_Pin GPIO_PIN_6
#define FR_ENC2_GPIO_Port GPIOB
#define FR_ENC1_Pin GPIO_PIN_7
#define FR_ENC1_GPIO_Port GPIOB
#define SCL_Pin GPIO_PIN_8
#define SCL_GPIO_Port GPIOB
#define SDA_Pin GPIO_PIN_9
#define SDA_GPIO_Port GPIOB

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
