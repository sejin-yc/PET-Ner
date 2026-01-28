FROM gradle:7.6-jdk17 AS builder
WORKDIR /build

# 그래들 파일 복사 (캐시 효율을 위해)
COPY build.gradle settings.gradle ./
COPY src ./src

# 빌드 (테스트 제외하고 빠르게)
RUN gradle bootJar -x test --no-daemon

# 실행 단계
FROM eclipse-temurin:17-jdk-jammy
WORKDIR /app

# 빌드 결과물 복사
COPY --from=builder /build/build/libs/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "--add-opens", "java.base/java.net=ALL-UNNAMED", "-jar", "app.jar"]
