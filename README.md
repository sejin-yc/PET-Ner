# 🐱 PET-Ner

### AI 기반 돌봄 공백 해소를 위한 반려묘 케어 자율주행 로봇

> SSAFY 공통프로젝트 우수상 (2위)\
> Team 밍숭맹수

------------------------------------------------------------------------

## 📌 프로젝트 개요

PET-Ner는 1인 가구 증가로 인한 **반려묘 돌봄 공백 문제 해결**을 목표로
제작된 AI 기반 자율주행 케어 로봇입니다.

로봇은 실내를 순찰(Patrol)하며 반려묘 상태를 판단하고, 필요 시 급식 / 물
교체 / 화장실 청소 / 영상 기록 등의 Task를 수행합니다.

------------------------------------------------------------------------

## 🏗 System Architecture

### 3-Layer Distributed Architecture

  계층               역할                          하드웨어
  ------------------ ----------------------------- ------------------
  AI Layer           Vision 추론, VLA, 회귀 모델   Jetson Orin Nano
  Navigation Layer   SLAM, Nav2, Waypoint 제어     Raspberry Pi 5
  Control Layer      실시간 모터 제어              STM32

### 주요 특징

-   연산 특성 기반 계층 분리
-   AI 추론과 실시간 제어 루프 분리
-   Twist-mux 기반 제어 우선순위 관리
-   상태 전이 기반 Task Orchestration

------------------------------------------------------------------------

## 🚗 Navigation & Precision Docking

### 🧭 2D LiDAR SLAM 기반 순찰

-   Nav2 기반 Waypoint Patrol
-   AMCL 기반 위치 추정
-   장애물 회피 및 경로 재계획

### 🎯 ArUco Marker 기반 정밀 도킹

-   Nav2 제어와 완전 분리된 근접 제어 루프
-   `/aruco/pose` 상대좌표 기반 제어
-   Heading → Lateral → Distance 순차 정렬
-   Pulse 기반 미세 제어 (Overshoot 최소화)
-   Deadband 설계로 진동 방지
-   미검출 시 재정렬 루프 설계

------------------------------------------------------------------------

## 🤖 AI Modules

### 🍚 사료 잔량 추정 파이프라인

YOLOv8n 기반 사료 영역(ROI) 탐지

EfficientNetV2-S Backbone 기반 잔량 회귀 추정

사료 잔량(g) 정량 예측

MAE ≈ 2~3%

자동 사료 보충량 계산 로직 

------------------------------------------------------------------------

### 🧠 Vision-Language-Action (VLA)

물 교체 / 화장실 청소 기능에서 사용

-   이미지 기반 상태 인식
-   고수준 Task 판단
-   Manipulation 명령 생성

------------------------------------------------------------------------

## 🔄 Task Flow

Waypoint Patrol\
→ ArUco Precision Alignment\
→ Task Execution (Feeding / Water / Cleaning)\
→ Status Report Transmission\
→ Resume Patrol

------------------------------------------------------------------------

## 🌐 Web Dashboard

-   실시간 스트리밍
-   수동 제어 (Joystick)
-   TTS 기능
-   영상 저장
-   사료 잔량 확인
-   Task 수동 실행
-   츄르 급여 기능

------------------------------------------------------------------------

## 🔧 Tech Stack

### Robotics

-   ROS2 Humble
-   Nav2
-   AMCL
-   TF2
-   ArUco
-   Twist-mux

### AI

-   PyTorch
-   YOLOv8
-   timm (Swin-Tiny)
-   Vision-Language-Action 모델

### Hardware

-   Jetson Orin Nano
-   Raspberry Pi 5
-   STM32
-   YDLiDAR
-   RealSense D435i
-   Mecanum Wheel Platform

------------------------------------------------------------------------

## 🏆 Achievements

-   SSAFY 공통프로젝트 2위 (우수상)
-   대규모 분산 로봇 시스템 통합 설계
-   AI-Navigation-Control 통합 아키텍처 구현

------------------------------------------------------------------------

## 📌 Future Work

-   Edge-optimized VLA 모델 경량화
-   Multi-Cat Identification
-   강화학습 기반 행동 최적화
-   클라우드 연동 로그 분석 시스템
