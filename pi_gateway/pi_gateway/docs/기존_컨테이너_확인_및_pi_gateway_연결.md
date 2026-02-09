# 기존 컨테이너(my_bot, my_bot_new) 확인 및 pi_gateway 연결

`docker ps`로 보이는 **my_bot**, **my_bot_new** 가 있을 때, ROS2 토픽이 어디서 나오는지·pi_gateway를 어떻게 붙일지 확인하는 방법입니다.

---

## 1. 지금 상황 정리

| 컨테이너 이름 | 이미지 | 비고 |
|---------------|--------|------|
| my_bot | ros:humble-ros-base | Humble 베이스만 있을 수 있음 (노드 없으면 토픽 없음) |
| my_bot_new | catbot_rpi_backup | SLAM·LiDAR 등이 여기서 돌 가능성 큼 |

`ros2 topic list`를 **my_bot** 안에서만 하면 `/scan`, `/odom`, `/tf`, `/map` 이 안 나올 수 있습니다. **my_bot_new** 안에서도 한 번 돌려 보세요.

---

## 2. my_bot_new 안에서 ROS2 토픽 확인

```bash
sudo docker exec -it my_bot_new bash -lc "source /opt/ros/humble/setup.bash && ros2 topic list"
```

필요하면 특정 토픽만:

```bash
sudo docker exec -it my_bot_new bash -lc "source /opt/ros/humble/setup.bash && ros2 topic list | grep -E '/scan|/odom|/tf|/map'"
```

- 여기서 토픽이 나오면 → SLAM·LiDAR(또는 관련 노드)가 **my_bot_new** 에서 도는 것.
- 노드 목록도 보려면:

```bash
sudo docker exec -it my_bot_new bash -lc "source /opt/ros/humble/setup.bash && ros2 node list"
```

---

## 3. 컨테이너 네트워크 모드 확인 (pi_gateway 붙일 때 필요)

pi_gateway를 **같은 DDS**로 붙이려면, 기존 컨테이너가 **host** 인지 **bridge** 인지 알면 좋습니다.

```bash
sudo docker inspect my_bot_new --format '{{.HostConfig.NetworkMode}}'
sudo docker inspect my_bot     --format '{{.HostConfig.NetworkMode}}'
```

- **host** → pi_gateway도 `--network host` 로 띄우면 같은 호스트에서 DDS 통신 가능.
- **default** (bridge) → pi_gateway를 **host** 로 띄우면, 호스트 네트워크에서 DDS를 쓰므로 **my_bot_new** 가 bridge만 쓰면 서로 발견이 안 될 수 있음. 그때는 pi_gateway도 **같은 bridge 네트워크**에 붙이거나, SLAM 담당자에게 “host 모드로 바꿀 수 있나?” 여쭤보면 됨.

---

## 4. ROS_DOMAIN_ID 확인 (선택)

컨테이너 안에서 기본 도메인 쓰는지 확인:

```bash
sudo docker exec -it my_bot_new bash -lc "source /opt/ros/humble/setup.bash && echo ROS_DOMAIN_ID=\${ROS_DOMAIN_ID:-0}"
```

- 안 나오거나 0 이면 → pi_gateway는 **ROS_DOMAIN_ID=0** (또는 생략)으로 두면 됨.

---

## 5. pi_gateway 띄울 때 (정리)

- **my_bot_new** 가 **host** 이고, 토픽이 **my_bot_new** 에서 나온다면:
  - pi_gateway도 **host** 로 띄우고 **ROS_DOMAIN_ID=0** 쓰면, 같은 파이에서 ROS 토픽으로 통신될 가능성이 큼.
- **my_bot_new** 가 **bridge** 이면:
  - pi_gateway를 **같은 네트워크**에 붙이거나, SLAM·LiDAR 쪽을 host로 맞추는 게 필요함.

---

## 6. 한 번에 복사해서 쓸 명령어

```bash
# 1) 토픽이 어느 컨테이너에서 나오는지 (my_bot_new 권장)
sudo docker exec -it my_bot_new bash -lc "source /opt/ros/humble/setup.bash && ros2 topic list"

# 2) 네트워크 모드 (host 인지 확인)
sudo docker inspect my_bot_new --format '{{.HostConfig.NetworkMode}}'

# 3) pi_gateway는 host + ROS_DOMAIN_ID=0 으로 실행
# (이미지 빌드 후)
sudo docker run -d --name pi_gateway \
  --device /dev/serial0:/dev/serial0 \
  -p 8000:8000 \
  -e UART_ENABLED=1 \
  -e UART_PORT=/dev/serial0 \
  -e ROS_ENABLED=1 \
  -e ROS_DOMAIN_ID=0 \
  --network host \
  --restart unless-stopped \
  pi_gateway:humble
```

**요약:**  
- ROS2 토픽 확인은 **my_bot_new** 안에서 `source /opt/ros/humble/setup.bash` 한 뒤 `ros2 topic list`  
- pi_gateway는 **host** + **ROS_DOMAIN_ID=0** 으로 띄우면, 같은 파이에서 SLAM·LiDAR와 ROS 토픽으로 통신할 수 있음.
