const board = document.querySelector('.infinite-board');
const BOARD_SIZE = 10000;
board.style.width = `${BOARD_SIZE}px`;
board.style.height = `${BOARD_SIZE}px`;
const centerX = window.innerWidth / 2 - BOARD_SIZE / 2;
const centerY = window.innerHeight / 2 - BOARD_SIZE / 2;
board.style.transform = `translate(${centerX}px, ${centerY}px)`;
let boardX = centerX, boardY = centerY;
let isDraggingBoard = false;
let dragStartX, dragStartY;

board.addEventListener('mousedown', (e) => {

    if (e.target === board) {
        isDraggingBoard = true;
        dragStartX = e.clientX - boardX;
        dragStartY = e.clientY - boardY;
    }
});

board.addEventListener('contextmenu', (e) => {
    e.preventDefault();
  });

document.addEventListener('mousemove', (e) => {
    if (isDraggingBoard) {
        boardX = e.clientX - dragStartX;
        boardY = e.clientY - dragStartY;
        board.style.transform = `translate(${boardX}px, ${boardY}px)`;
    }
});

document.addEventListener('mouseup', () => {
    isDraggingBoard = false;
});
