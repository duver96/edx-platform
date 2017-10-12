/*
    Ensuring collapsible and accessible components on multiple
    screen sizes for the responsive lms header.
*/

$(document).ready(function() {
    // Displaying the user dropdown
    $('.toggle-user-dropdown').click(function() {
      var $dropdownMenu = $('.global-header .nav-item .dropdown-user-menu');
      if ($dropdownMenu.is(':visible')) {
        $dropdownMenu.hide();
      } else {
        $dropdownMenu.show();
        $dropdownMenu.find('.dropdown-item')[0].focus();
      }
    });

    // Functionality for the hamburger menu on mobile
    var $hamburgerMenu = $('.hamburger-menu');
    $hamburgerMenu.click(function() {
        $('.nav-links').toggleClass('nav-links-expanded');
        $('.hamburger-menu').toggleClass('open');
    });

    // Hide hamburger menu if no nav items
    if ($('.nav-item').size() === 0){
        $hamburgerMenu.css('display', 'none');
    };
});

// Ensure click away hides the dropdown
$(window).click(function(e) {
  if (!$(e.target).is('.dropdown-item, .toggle-user-dropdown')){
    $('.global-header .nav-item .dropdown-user-menu').hide();
  }
});

// Accessibility for hamburger menu
$(document).on('keydown', function(e) {
    if (e.keyCode === 13 && $(e.target).hasClass('hamburger-menu')) {
        $(e.target).click();
    }
});

// Accessibility for user dropdown
$(document).on('keydown', function(e) {
    var isToggle =  $(e.target).hasClass('toggle-user-dropdown');
    var isDropdownOption = $(e.target).children().hasClass('dropdown-item');

    // Open dropdown menu on enter or space click
    if ((e.keyCode === 13 || e.keyCode === 32) && isToggle) {
        $(e.target).click();
        $('.dropdown-item:first').parent().focus();
    }

    // Enable arrow functionality
    if ((e.keyCode === 38 || e.keyCode === 40) && (isToggle || isDropdownOption)) {
        var isNext = e.keyCode === 40;
        if (isNext && isToggle) {
           $('.dropdown-item:first').parent().focus();
        } else if (isNext) {
            $(e.target).next().focus();
        } else if (!isNext && !isToggle) {
           $(e.target).prev().focus();
        }
        e.preventDefault(); // Don't let the screen scroll on navigation
    }

    // Allow escape to clear out of the dropdown
    if (e.keyCode === 27 && (isDropdownOption || isToggle)) {
        $('.global-header .nav-item .dropdown-user-menu').hide();
        $('.toggle-user-dropdown').focus();
    }
});