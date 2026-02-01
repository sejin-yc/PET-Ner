import React, { useEffect, useRef, useState } from "react";
import styled from 'styled-components';

const MAP_CONFIG = {
    imageUrl: "https://i14c203.p.ssafy.io/uploads/cat_bot_map_final.png",
    resolution: 0.05,   // 1픽셀당 0.05m (5cm)
    originX: -1.51,     // 맵의 원점 X (meters)
    originY: -0.84,     // 맵의 원점 Y (meters)
    originWidth: 64,    // PGM 파일 너비 (픽셀) - 파일 헤더 정보
    originHeight: 62    // PGM 파일 높이 (픽셀) - 파일 헤더 정보
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
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    background-color: white;
    image-rendering: pixelated;
`

const Map2D = ({robotX = 0, robotY = 0, robotTheta = 0}) => {
    const containerRef = useRef(null);
    const canvasRef = useRef(null);
    const [image, setImage] = useState(null);

    useEffect(() => {
        const img = new Image();
        img.src = MAP_CONFIG.imageUrl;
        img.crossOrigin = "Anonymous";
        img.onload = () => setImage(img);
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !image || !container) return;

        const ctx = canvas.getContext('2d');

        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;

        canvas.width = containerWidth;
        canvas.height = containerHeight;

        const scaleX = containerWidth / MAP_CONFIG.originWidth;
        const scaleY = containerHeight / MAP_CONFIG.originHeight;
        const scale = Math.min(scaleX, scaleY);

        const mapDisplayWidth = MAP_CONFIG.originWidth * scale;
        const mapDisplayHeight = MAP_CONFIG.originHeight * scale;
        const offsetX = (containerWidth - mapDisplayWidth) / 2;
        const offsetY = (containerHeight - mapDisplayHeight) / 2;

        ctx.imageSmoothingEnabled = false;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(
            image,
            0, 0, MAP_CONFIG.originWidth, MAP_CONFIG.originHeight,
            offsetX, offsetY, mapDisplayWidth, mapDisplayHeight
        );

        drawRobot(ctx, robotX, robotY, robotTheta, scale, offsetX, offsetY);
    }, [image, robotX, robotY, robotTheta]);

    const drawRobot = (ctx, realX, realY, theta, scale, offsetX, offsetY) => {
        const rawPixelX = (realX - MAP_CONFIG.originX) / MAP_CONFIG.resolution;
        const rawPixelY = (realY - MAP_CONFIG.originY) / MAP_CONFIG.resolution;

        const finalX = (rawPixelX * scale) + offsetX;
        const finalY = (MAP_CONFIG.originHeight - rawPixelY) * scale + offsetY;

        ctx.save();
        ctx.translate(finalX, finalY);
        ctx.rotate(-theta);

        const robotSize = 4 * (scale / 5);

        ctx.beginPath();
        ctx.arc(0, 0, robotSize, 0, 2*Math.PI);
        ctx.fillStyle = '#ef4444';
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(robotSize*1.6, 0);
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.restore();
    };

    return (
        <MapContainer ref={containerRef}>
            <Canvas ref={canvasRef} />
        </MapContainer>
    );
};

export default Map2D;