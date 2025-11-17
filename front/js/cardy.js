// Board logic
const board = document.querySelector('.board');
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

    if (e.target === board && e.shiftKey) {
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


// Card logic
let isDraggingCard = false;
let draggedCard = null;
let cardX, cardY;
let cardDragStartX, cardDragStartY;

console.log('cardy.js loaded');

// Card expansion on double-click
document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('dblclick', function(e) {
        if (e.target.closest('.resize-handle')) return;
        if (e.target.closest('.claudy-button')) return;

        if (this.classList.contains('expanded')) {
            this.classList.remove('expanded');
            this.style.width = '300px';
            this.style.height = '150px';
        } else {
            this.classList.add('expanded');
        }
    });
  });

// Card dragging
document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('contextmenu', (e) => {
        e.preventDefault();
    });

    card.addEventListener('mousedown', (e) => {
        if (!e.shiftKey) return;  // hold Shift to drag
        isDraggingCard = true;
        draggedCard = card;

        cardX = parseInt(getComputedStyle(card).left);
        cardY = parseInt(getComputedStyle(card).top);

        cardDragStartX = e.clientX - cardX;
        cardDragStartY = e.clientY - cardY;
        e.stopPropagation();
    });
});

document.addEventListener('mousemove', (e) => {

    if (isDraggingCard) {
        cardX = e.clientX - cardDragStartX;
        cardY = e.clientY - cardDragStartY;
        draggedCard.style.left = cardX + 'px';
        draggedCard.style.top = cardY + 'px';
    }
});

document.addEventListener('mouseup', () => {
    isDraggingCard = false;
    draggedCard = null;
});

// Card resizing
let isResizing = false;
let resizingCard = null;
let resizeStartX, resizeStartY, startWidth, startHeight, startLeft, startTop;
const minWidth = 400;
const minHeight = 200;
document.querySelectorAll('.resize-handle').forEach(handle => {
  handle.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    isResizing = true;
    resizingCard = handle.closest('.card');
    resizeStartX = e.clientX;
    resizeStartY = e.clientY;
    startWidth = resizingCard.offsetWidth;
    startHeight = resizingCard.offsetHeight;
    startLeft = resizingCard.offsetLeft;
    startTop = resizingCard.offsetTop;
  });
});
document.addEventListener('mousemove', (e) => {
  if (isResizing) {
    const deltaX = e.clientX - resizeStartX;
    const deltaY = e.clientY - resizeStartY;
    const newWidth = Math.max(minWidth, startWidth + deltaX);
    const newHeight = Math.max(minHeight, startHeight + deltaY);
    resizingCard.style.width = newWidth + 'px';
    resizingCard.style.height = newHeight + 'px';
    const newLeft = Math.max(startLeft, startLeft + 0.5*deltaX);
    const newTop = Math.max(startTop, startTop + 0.5*deltaY);
    resizingCard.style.left = newLeft + 'px';
    resizingCard.style.top = newTop + 'px';
  } 
});
document.addEventListener('mouseup', () => {
  isResizing = false;
});