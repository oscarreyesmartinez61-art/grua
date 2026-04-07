from machine import ADC, Pin, mem32
import time
from machine import Pin, PWM
import time

########################## REGISTROS GPIO ESP32
GPIO_OUT_W1TS = 0x3FF44008 # Direccion del registro para poner en ALTO (ON) los pines
GPIO_OUT_W1TC = 0x3FF4400C # Direccion del registro para poner en BAJO (OFF) los pines

def led_on(pin):
    mem32[GPIO_OUT_W1TS] = (1 << pin) # Enciende el pin desplazando un bit a su posicion en memoria

def led_off(pin):
    mem32[GPIO_OUT_W1TC] = (1 << pin) # Apaga el pin desplazando un bit a su posicion en memoria
###########################


############################ ANTIREBOTE POR SOFTWARE
def leer_boton(boton):
    if boton.value(): # Si el boton detecta una pulsacion (valor 1)
        time.sleep_ms(20) # Espera 20 milisegundos para ignorar el ruido electrico
        if boton.value(): # Si despues del tiempo sigue presionado
            while boton.value(): # Mientras el boton se mantenga presionado
                pass # No hace nada, espera a que el usuario lo suelte
            return True # Retorna verdadero indicando una pulsacion valida
    return False # Retorna falso si no hubo pulsacion
###########################

########################### DEFINICION DE POT, SERVOS,LEDs Y BOTONES
pot1 = ADC(Pin(34)) 
pot1.width(ADC.WIDTH_12BIT)# 12 bits para movimientos suaves y precision
pot1.atten(ADC.ATTN_11DB)  # rango completo

pot2 = ADC(Pin(35)) 
pot2.width(ADC.WIDTH_12BIT)# 12 bits para movimientos suaves y precision
pot2.atten(ADC.ATTN_11DB)  # rango completo

servo1 = PWM(Pin(18), freq=50)
servo2 = PWM(Pin(19), freq=50)

btn_manual = Pin(25, Pin.IN, Pin.PULL_UP) # Boton pin 25 con pull-UP
btn_auto = Pin(26, Pin.IN, Pin.PULL_UP) # Boton pin 26 con pull-UP
btn_retorno = Pin(27, Pin.IN, Pin.PULL_UP) # Boton pin 27 con pull-UP

#leds
Pin(2, Pin.OUT) # pin 2 como salida
Pin(4, Pin.OUT) # pin 4 como salida
buzzer = PWM(Pin(15))# BUZZER Pin 15
buzzer.freq(1000)
buzzer.duty(0)

LED_VERDE = 2
LED_ROJO = 4
############################


############################ INTERRUPCION MODO AUTO ANTIRREBOTE

auto_requested = False
_last_auto_irq = 0  # para anti-rebote de IRQ (ms)
AUTO_IRQ_DEBOUNCE_MS = 300

def _auto_irq_handler(pin):
    global auto_requested, _last_auto_irq
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_auto_irq) > AUTO_IRQ_DEBOUNCE_MS:
        _last_auto_irq = now
        # Toggle behavior: if we're inside Simón (auto_active) then set request to exit,
        # otherwise set request to start Simón. We'll use the same flag for both.
        auto_requested = True
   
btn_auto.irq(trigger=Pin.IRQ_FALLING, handler=_auto_irq_handler) #(solo marca la petición)
############################ 


############################ DEF DEL MODO MANUAL COMO VARIABLE GLOBAL
def mover_servo(servo, valor_adc):
    min_duty = 30
    max_duty = 120
    duty = int((valor_adc / 4095) * (max_duty - min_duty) + min_duty)
    servo.duty(duty)
################################


################################ FUNCION DEL BUZZER COMO PITUDO
def buzzer_encendido():
    buzzer.freq(3000)   # frecuencia continua
    buzzer.duty(512)    # intensidad media

# Función para apagar el buzzer
def buzzer_apagado():
    buzzer.duty(0)   
        
          
################################


############################ MODO MANUAL 
def MODO_MANUAL():

    def mover_servo(servo, valor_adc):#valor representa posicion del potenciometro

        min_duty = 30    # ~0.5 ms
        max_duty = 120   # ~2.5 ms

        duty = int((valor_adc / 4095) * (max_duty - min_duty) + min_duty)
        servo.duty(duty)
    led_on(LED_VERDE)
    val1 = pot1.read()
    val2 = pot2.read()

    mover_servo(servo1, val1)
    mover_servo(servo2, val2)
    print("Pot1:", val1 , "|" ,"Pot2:", val2)

    time.sleep(0.1) # tiempo para evitar ruido y movimientos bruscos
###############################


############################### MODO AUTO (SECUENCIA)
def MOD_AUTO(inicio_base, inicio_brazo):

    led_off(LED_VERDE)
    led_on(LED_ROJO)
    buzzer_encendido()

    print("Modo automático activado")
    posiciones = [
        (1000, 3000),
        (2048, 1024),
        (3500, 2500),
        (500, 4095),
        (3000, 1500),
        (3200, 4000),
        (200,3001)
    ]

    # Posición inicial actual
    base_actual = inicio_base
    brazo_actual = inicio_brazo

    for pos_base, pos_brazo in posiciones:
        # Mover de la posición actual a la siguiente paso a paso
        pasos = 30  # ancho de paso como en especiales

        for i in range(1, pasos + 1):
            # Si se activa retorno, salir inmediatamente
            # si no se activa el retorno continua con la secuencia
            if retorno_requested:
                print("Retorno solicitado, saliendo de modo automático")
                led_off(LED_ROJO)
                led_on(LED_VERDE)
                return  # termina MOD_AUTO y vuelve al loop principal


        # interpolación lineal(solamente para moverse, no interfiere en la secuencia)
            base = int(base_actual + (pos_base - base_actual) * i / pasos)
            brazo = int(brazo_actual + (pos_brazo - brazo_actual) * i / pasos)
            mover_servo(servo1, base)
            mover_servo(servo2, brazo)
            time.sleep(0.02)  # velocidad del movimiento
    
        base_actual = pos_base
        brazo_actual = pos_brazo
    # INTERPOLACION PARA REGRESAR A LA ULTIMA POSICION DEL MODO MANUAL    
    pasos = 50
    for i in range(1, pasos+1):
        base = int(base_actual + (inicio_base - base_actual) * i / pasos)
        brazo = int(brazo_actual + (inicio_brazo - brazo_actual) * i / pasos)
        mover_servo(servo1, base)
        mover_servo(servo2, brazo)
        time.sleep(0.02)

    mover_servo(servo1, base)
    mover_servo(servo2, brazo)

    led_off(LED_ROJO)
    led_on(LED_VERDE)
    buzzer_apagado()

    print("Modo automático finalizado, regresando a manual")
####################################


#####################################  MODO RETORNO VOLVER A LA POSICION 500 QUE LE DIMOS
def MOD_RETORNO(pos_base_objetivo, pos_brazo_objetivo):

    led_off(LED_VERDE)
    led_on(LED_ROJO)
    buzzer_encendido()

    """
    Mueve los servos desde la posición actual a la posición objetivo de forma suave.
    """
    print("MODO RETORNO ACTIVADO, CUIDADO")
    # Leer posición actual de los servos desde los potenciómetros

    base_actual = pot1.read()
    brazo_actual = pot2.read()

    pasos = 50  # cantidad de pasos para suavizar
########pasos y velocidad mientras se hace el retorno
    for i in range(1, pasos + 1):
        # interpolación lineal
        base = int(base_actual + (pos_base_objetivo - base_actual) * i / pasos)
        brazo = int(brazo_actual + (pos_brazo_objetivo - brazo_actual) * i / pasos)

        mover_servo(servo1, base)
        mover_servo(servo2, brazo)

        time.sleep(0.02)  # controla la velocidad del movimiento mientras se hace el retorno
########
    # Asegurar que queden exactamente en la posición final
    mover_servo(servo1, pos_base_objetivo)
    mover_servo(servo2, pos_brazo_objetivo)
    time.sleep(5)

    led_on(LED_VERDE)
    led_off(LED_ROJO)
    buzzer_apagado()
    print("SALIENDO MODO RETOCESO")
####################################


############################### MENU
def PRESIONAR_INICIAR():
    print("") # Salto de linea
    print("\n=== PRESIONAR MODO MANUAL PARA INICIAR ===") # Titulo del menu
    print("="*30) # Linea separadora

    while True: # Bucle infinito hasta que se elija una opcion
        if leer_boton(btn_manual): # Si el Jugador 1 presiona su primer boton
            break # Sale del bucle
################################


#################################CREAR LA INTERRUPCION MODO RETORNO

retorno_requested = False
_last_retorno_irq = 0  # para anti-rebote de IRQ (ms)
RETORNO_IRQ_DEBOUNCE_MS = 300

def _retorno_irq_handler(pin):
    global retorno_requested, _last_retorno_irq
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_retorno_irq) > RETORNO_IRQ_DEBOUNCE_MS:
        _last_retorno_irq = now
        
        retorno_requested = True
   
btn_retorno.irq(trigger=Pin.IRQ_FALLING, handler=_retorno_irq_handler) #(solo marca la petición)
##################################


################################ LOOP PRINCIPAL
while True: # Bucle infinito del programa

    PRESIONAR_INICIAR()
    print("\n=== JUEGO INICIADO ===")
    print("\n=== MODO MANUAL INICIADO ===")

    while True: #### LOOP PRINCIPAL DEL JUEGO

        # Si la IRQ marcó Modo auto fuera de partida, atenderla aquí
        if auto_requested:
            # consumir la petición de inicio Modo auto
            auto_requested = False
            base_manual = pot1.read()
            brazo_manual = pot2.read()

            MOD_AUTO(inicio_base=base_manual, inicio_brazo=brazo_manual)
            print("\n MODO AUTO ACTIVADO...\n")
        
        if retorno_requested:
            retorno_requested = False
            mover_servo(servo1, 0)
            mover_servo(servo2, 0)
            MOD_RETORNO(0, 0)

        MODO_MANUAL()
