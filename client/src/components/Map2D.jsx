import React, { useEffect, useRef, useState } from "react";
import styled from 'styled-components';

const MAP_CONFIG = {
    imageUrl: "https://i14c203.p.ssafy.io/uploads/cat_bot_map_final.png",
    resolution: 0.05,   // 1픽셀당 0.05m (5cm)
    originX: -1.51,     // 맵의 원점 X (meters)
    originY: -0.84,     // 맵의 원점 Y (meters)
    width: 64,          // PGM 파일 너비 (픽셀) - 파일 헤더 정보
    height: 62          // PGM 파일 높이 (픽셀) - 파일 헤더 정보
};

const MapContainer = styled.div`
    width: 100%;
    height: 100%,
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #f0f0f0;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
`;

const Canvas = styled.canvas`
    max-width: 100%;
    max-height: 100%;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
`

const Map2D = ({robotX = 0, robotY = 0, robotTheta = 0}) => {
    const canvasRef = useRef(null);
    const [image, setImage] = useState(null);

    useEffect(() => {
        const img = new Image();
        img.src = MAP_CONFIG.imageUrl;
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

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

        const pixelX = (robotX - MAP_CONFIG.originX) / MAP_CONFIG.resolution;
        const pixelYRaw = (robotY - MAP_CONFIG.originY) / MAP_CONFIG.resolution;
        const pixelY = canvas.height = pixelYRaw;

        drawRobot(ctx, pixelX, pixelY, robotTheta);
    }, [image, robotX, robotY, robotTheta]);

    const drawRobot = (ctx, x, y, theta) => {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(-theta);

        ctx.beginPath();
        ctx.arc(0, 0, 5, 0, x * Math.PI);
        ctx.fillStyle = 'red';
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(8, 0);
        ctx.strokeStyle = 'yellow';
        ctx.lineWidth = 2;
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