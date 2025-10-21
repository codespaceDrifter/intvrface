let isDraggingCard = false;
let draggedCard = null;
let cardX, cardY;
let cardDragStartX, cardDragStartY;

console.log('card.js loaded');

document.querySelectorAll('.claudy-card').forEach(card => {
    card.addEventListener('dblclick', function(e) {
      if (e.target.closest('.resize-handle')) return;
      
      if (this.classList.contains('expanded')) {
        this.classList.remove('expanded');
        this.style.width = '300px';
        this.style.height = '150px';
      } else {
        this.classList.add('expanded');
      }
    });
  });



document.querySelectorAll('.claudy-card').forEach(card => {
    card.addEventListener('contextmenu', (e) => {
        e.preventDefault();
    });

    card.addEventListener('mousedown', (e) => {
        if (e.button !== 2) return;

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


let isResizing = false;
let resizingCard = null;
let resizeStartX, resizeStartY, startWidth, startHeight;

document.querySelectorAll('.resize-handle').forEach(handle => {
  handle.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    isResizing = true;
    resizingCard = handle.closest('.claudy-card');
    resizeStartX = e.clientX;
    resizeStartY = e.clientY;
    startWidth = resizingCard.offsetWidth;
    startHeight = resizingCard.offsetHeight;
  });
});

document.addEventListener('mousemove', (e) => {
  if (isResizing) {
    const deltaX = e.clientX - resizeStartX;
    const deltaY = e.clientY - resizeStartY;
    resizingCard.style.width = (startWidth + 2*deltaX) + 'px';
    resizingCard.style.height = (startHeight + 2*deltaY) + 'px';
  }
});

document.addEventListener('mouseup', () => {
  isResizing = false;
});