#include <iostream>
#include <SFML/Graphics.hpp>


int main() {
    sf::VideoMode mode(642, 640);
    sf::RenderWindow window(mode, "Painter");

    sf::Texture backgroundTexture;
    backgroundTexture.loadFromFile("background.png");

    sf::Sprite backgroundSprite(backgroundTexture);
    backgroundSprite.setPosition(0, 40);

    sf::CircleShape cursor(10);
    cursor.setFillColor(sf::Color::Black);
    cursor.setOrigin(10, 10);

    std::vector<sf::Color> colors = {
        sf::Color::White,
        sf::Color::Black,
        sf::Color::Red,
    };
    
    std::vector<sf::RectangleShape> swatches;

    int swatchOffset = 20;
    for (auto color : colors) {
        sf::RectangleShape swatch(sf::Vector2f(20, 20));
        swatch.setFillColor(color);
        swatch.setOutlineColor(sf::Color(230, 230, 230));
        swatch.setOutlineThickness(2);
        swatch.setPosition(swatchOffset, 10);
        swatches.push_back(swatch);

        swatchOffset += 20;
    }

    sf::RenderTexture canvas;
    canvas.create(600, 500);
    canvas.clear(sf::Color::White);

    sf::Vector2f canvasOffset(20, 60);
    sf::Sprite canvasSprite(canvas.getTexture());
    canvasSprite.setPosition(canvasOffset);

    while (window.isOpen()) {
        sf::Event evt;
        if (window.pollEvent(evt)) {
            if (evt.type == sf::Event::Closed) {
                window.close();
            }
            if (evt.type == sf::Event::MouseButtonPressed) {
                if (evt.mouseButton.button == sf::Mouse::Left) {
                    for (const auto& swatch : swatches) {
                        if (swatch.getGlobalBounds().contains(evt.mouseButton.x, evt.mouseButton.y)) {
                            cursor.setFillColor(swatch.getFillColor());
                        }
                    }
                }
        }

        sf::Vector2i mousePos = sf::Mouse::getPosition(window);
        //std::cout << mousePos.x << ", " << mousePos.y << std::endl;
        
        if (sf::Mouse::isButtonPressed(sf::Mouse::Left)) {
            cursor.setPosition(sf::Vector2f(mousePos)- canvasOffset);
            canvas.draw(cursor);
            canvas.display();
        }


        window.clear(sf::Color::White);

        for (const auto& swatch : swatches) {
            window.draw(swatch);
        }
        window.draw(backgroundSprite);
        window.draw(canvasSprite);

        cursor.setPosition(sf::Vector2f(mousePos));
        window.draw(cursor);
        window.display();
    }
}
