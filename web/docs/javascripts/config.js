// Mermaid configuration
mermaid.initialize({
  startOnLoad: true,
  theme: 'default',
  securityLevel: 'loose',
  flowchart: {
    useMaxWidth: true,
    htmlLabels: true,
    curve: 'basis'
  },
  themeVariables: {
    primaryColor: '#009688',
    primaryTextColor: '#fff',
    primaryBorderColor: '#00796B',
    lineColor: '#757575',
    secondaryColor: '#E0F2F1',
    tertiaryColor: '#B2DFDB'
  }
});

// Add smooth scroll behavior
document.documentElement.style.scrollBehavior = 'smooth';

// Add fade-in animation on scroll for cards
const observerOptions = {
  threshold: 0.1,
  rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, observerOptions);

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.md-card').forEach(card => {
    observer.observe(card);
  });
});
