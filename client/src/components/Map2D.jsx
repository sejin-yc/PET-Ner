import React, { useEffect, useRef, useState } from "react";
import styled from 'styled-components';

const MAP_CONFIG = {
    imageUrl: "/cat_bot_map_final.png",
    resolution: 0.05,   // 1픽셀당 0.05m (5cm)
    originX: -1.51,     // 맵의 원점 X (meters)
    originY: -0.84,     // 맵의 원점 Y (meters)
};

const MapContainer = styled.div`
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #e5e7eb;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
`;

const Canvas = styled.canvas`
    width: 100%;
    height: 100%;
    object-fit: contain;
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
        img.onload = () => {
            console.log("✅ 지도 이미지 로딩 성공:", img.width, "x", img.height);
            setImage(img);
        };
        img.onerror = () => {
            console.error("❌ 지도 이미지를 찾을 수 없습니다! public 폴더에 파일이 있는지 확인하세요:", MAP_CONFIG.imageUrl);
        };
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !image || !container) return;

        const draw = () => {
            const ctx = canvas.getContext('2d');

            const containerWidth = container.clientWidth;
            const containerHeight = container.clientHeight;

            canvas.width = containerWidth;
            canvas.height = containerHeight;

            const mapWidth = image.width;
            const mapHeight = image.height;

            const scaleX = containerWidth / mapWidth;
            const scaleY = containerHeight / mapHeight;
            const scale = Math.min(scaleX, scaleY);

            const mapDisplayWidth = mapWidth * scale;
            const mapDisplayHeight = mapHeight * scale;
            const offsetX = (containerWidth - mapDisplayWidth) / 2;
            const offsetY = (containerHeight - mapDisplayHeight) / 2;

            ctx.imageSmoothingEnabled = false;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(
                image,
                0, 0, mapWidth, mapHeight,
                offsetX, offsetY, mapDisplayWidth, mapDisplayHeight
            );
            drawRobot(ctx, robotX, robotY, robotTheta, scale, offsetX, offsetY, mapHeight);
        };

        const resizeObserver = new ResizeObserver(() => {
            draw();
        });

        resizeObserver.observe(container);
        draw();

        return () => resizeObserver.disconnect();
    }, [image, robotX, robotY, robotTheta]);

    const drawRobot = (ctx, realX, realY, theta, scale, offsetX, offsetY, mapHeight) => {
        const rawPixelX = (realX - MAP_CONFIG.originX) / MAP_CONFIG.resolution;
        const rawPixelY = (realY - MAP_CONFIG.originY) / MAP_CONFIG.resolution;

        const finalX = (rawPixelX * scale) + offsetX;
        const finalY = ((mapHeight - rawPixelY) * scale) + offsetY;

        ctx.save();
        ctx.translate(finalX, finalY);
        ctx.rotate(-theta);

        const robotSize = 15;

        ctx.beginPath();
        ctx.arc(0, 0, robotSize, 0, 2*Math.PI);
        ctx.fillStyle = 'rgba(59, 130, 246, 0.9)';
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 3;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(robotSize, 0);
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 3;
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