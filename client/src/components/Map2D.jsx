import React, { useEffect, useRef, useState } from "react";
import styled from 'styled-components';

const MAP_CONFIG = {
    imageUrl: "https://i14c203.p.ssafy.io/uploads/cat_bot_map_final.png",
    resolution: 0.05,   // 1픽셀당 0.05m (5cm)
    originX: -1.51,     // 맵의 원점 X (meters)
    originY: -0.84,     // 맵의 원점 Y (meters)
    originwidth: 64,          // PGM 파일 너비 (픽셀) - 파일 헤더 정보
    originheight: 62          // PGM 파일 높이 (픽셀) - 파일 헤더 정보
};

const MapContainer = styled.div`
    width: 100%;
    height: 100%,
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #e5e7eb;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
`;

const Canvas = styled.canvas`
    max-width: 95%;
    max-height: 95%;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    background-color: white;
    border: 1px solid #ccc;
`

const Map2D = ({robotX = 0, robotY = 0, robotTheta = 0}) => {
    const canvasRef = useRef(null);
    const [image, setImage] = useState(null);

    useEffect(() => {
        const img = new Image();
        img.src = MAP_CONFIG.imageUrl;
        img.crossOrigin = "Anonymous";
        img.onload = () => {
            setImage(img);
            console.log("🗺️ 맵 이미지 로드 완료:", img.width, img.height);
        };
        img.onerror = () => console.error("❌ 맵 이미지를 찾을 수 없습니다. (uploads 폴더 확인)");
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !image) return;

        const ctx = canvas.getContext('2d');

        canvas.width = image.width;
        canvas.height = image.height;

        // (1) 배경 지우기 & 지도 그리기
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

        const scaleX = image.width / MAP_CONFIG.originWidth;
        const scaleY = image.heigt / MAP_CONFIG.originheight;

        // (2) 좌표 변환
        const pixelX = (robotX - MAP_CONFIG.originX) / MAP_CONFIG.resolution;
        const pixelY = (robotY - MAP_CONFIG.originY) / MAP_CONFIG.resolution;
        const finalX = pixelX * scaleX;
        const finalY = canvas.height - (pixelY * scaleY);

        // (3) 로봇 그리기
        drawRobot(ctx, finalX, finalY, robotTheta, Math.max(scaleX, 1));
    }, [image, robotX, robotY, robotTheta]);

    const drawRobot = (ctx, x, y, theta, scale) => {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(-theta);

        const size = 5 * scale;

        ctx.beginPath();
        ctx.arc(0, 0, size, 0, 2 * Math.PI);
        ctx.fillStyle = '#ef4444';
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2 * (scale * 0.5);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(size * 1.5, 0);
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2 * (scale * 0.5);
        ctx.stroke();

        ctx.restore();
    };

    return (
        <MapContainer>
            <Canvas ref={canvasRef} />
        </MapContainer>
    );
};

export default Map2D;