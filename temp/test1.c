/* Program to calculate what year someone will turn a specific age */
#include <stdio.h>
#define TARGET_AGE 65

int year1, year2;

int calcYear(int year1);

// int main(int arg, char *argv[])
int main(void)
  {
    // Ask the user for the birth year
    printf("What year was the subject born? ");
    printf("Enter as a 4-digit year (YYYY): ");
    scanf(" %d", &year1);
  
    // Calculate the future year and display it
    year2 = calcYear(year1);
  
    printf("Someone born in %d will be %d in %d.\n", year1, TARGET_AGE, year2);
  
    return 0;
  }

/* The function to get the future year */
int calcYear(int year1)
  {
    return (year1 + TARGET_AGE);
  }

