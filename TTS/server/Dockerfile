FROM gradle:7.6-jdk17 AS builder
WORKDIR /build

# 그래들 파일 복사 (캐시 효율을 위해)
COPY build.gradle settings.gradle ./

# 소스 코드 없이 의존성만 미리 다운로드
RUN gradle dependencies --no-daemon || return 0

# 실제 소스 복사 및 빌드
COPY src ./src
RUN gradle clean bootJar -x test --no-daemon

# 실행 단계
FROM eclipse-temurin:17-jdk-jammy
WORKDIR /app

# 컨테이너 OS 시간대를 한국 시간(KST)으로 설정
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 빌드 결과물 복사
COPY --from=builder /build/build/libs/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "--add-opens", "java.base/java.net=ALL-UNNAMED", "-Djava.security.egd=file:/dev/./urandom", "-jar", "app.jar"]