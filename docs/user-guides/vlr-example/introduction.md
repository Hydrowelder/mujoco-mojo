# Vertically Landing Rocket

!!! abstract

    This guide will walk you through the complete definition of a model using MuJoCo. In the example, we will build a model of a set of landing gear for a vertically landing model rocket. This model's construction follows a more object oriented approach than the previous example.

    <figure markdown="span">
        ![Completed model preview](./video.gif){ width="50%" height="auto" }
        <figcaption>The visual result of the completed model: the rocket has four landing gear equally spaced around its radius. A spring-damper is located on each leg to absorb the impact.</figcaption>
    </figure>

    This example is based on work I performed in the writing of [this paper](https://www.ideals.illinois.edu/items/128732).
