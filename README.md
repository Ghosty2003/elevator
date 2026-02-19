# Elevator Dispatch System

## Overview

This project implements a multi-elevator dispatch system with a controllable graphical elevator interface built using Qt. The system simulates elevator scheduling logic and provides a user-friendly UI to manually operate a small elevator unit. It demonstrates core concepts in task scheduling, state management, and real-time system interaction.

## Features

- Multi-elevator dispatch algorithm

- Real-time elevator state monitoring

- Interactive Qt-based elevator control panel

- Floor request handling (internal and external calls)

- Direction-aware scheduling

- Simulation of elevator movement and door status

## System Architecture

The system consists of two main components:

### 1. Dispatch Core

Handles:

- Floor request allocation

- Elevator state tracking

- Direction-based optimization

- Basic scheduling strategy (e.g., nearest-car or priority-based)

### 2. Elevator UI (Qt-Based)

Provides:

- Buttons for floor selection

- Open/Close door controls

- Current floor display

- Movement direction indicator

- Real-time status updates

## Technologies Used

- C++ 

- Qt Framework (Qt Widgets / Qt Creator)

- Event-driven architecture

